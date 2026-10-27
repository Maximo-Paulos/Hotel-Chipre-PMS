# Product Definition — Hotel Chipre PMS (SaaS Platform)

> Product-level contract for the **multi-tenant SaaS PMS** we are building and selling.
> This is NOT a single-hotel profile. Each subscribed hotel configures itself inside the product — see [hotel-onboarding-data.md](hotel-onboarding-data.md).
> Related: [roadmap.md](roadmap.md), [architecture-audit.md](architecture-audit.md), [security-baseline.md](security-baseline.md), [master-plan-pilot-to-public.md](master-plan-pilot-to-public.md).

---

## 1. Purpose & non-goals

### 1.1 What this product is
A multi-tenant SaaS Property Management System for hotels, covering reservations, rooms, guests, check-in/out, payments, OTA integration, and AI-assisted operations. Each subscribed hotel runs in isolated tenant scope (`hotel_id`) on a shared platform.

### 1.2 What it is NOT (platform-level non-goals)
TODO(owner) confirm/extend. Default non-goals unless owner says otherwise: full accounting, marketing automation, CRM campaigns, public booking-engine for the hotel website, housekeeping mobile app, automated price changes, competitor-price optimization, on-prem/self-hosted deployment model. The approved experimental pricing scope is recommendation-only and requires human approval before any tariff change.

### 1.3 Product vs per-hotel scope line
- **Product / platform**: architecture, tenancy, subscription tiers, default policies, AI guardrails, integrations catalogue, UI, security, operations.
- **Per-hotel**: hotel identity, rooms, categories, tariffs, policies (within allowed bounds), channels, payment accounts, users. See [hotel-onboarding-data.md](hotel-onboarding-data.md).

---

## 2. Target customer segments

Resolved 2026-04-16 (P-A).

### 2.1 Geographic scope at launch
- **Argentina first.**
- Product design must be prepared for Spanish-speaking LATAM expansion later (no AR-only hardcoding).
- Legal / compliance support at launch: **Argentina only**.
- Language at launch: **Spanish only**.
- Currency at launch: **ARS as primary**. Multi-currency is technically supported at the data layer; commercial support at launch is centered on ARS.

### 2.2 Hotel size range

- **Supported range at launch: 1–80 rooms.** The platform does NOT exclude single-room properties — a 1-room hotel can subscribe.
- **Primary commercial target:** small-to-mid hotels (typical focus ~6–80 rooms). This is marketing emphasis, not a gate.
- Drives subscription tier `room_limit` bounds (see §4) and solver expectations.
- Revised 2026-04-16 (P-A correction).

### 2.3 Hotel types in scope at launch
- Independent hotels.
- Boutique hotels.
- Apart-hotels / aparthoteles.
- Hostels **only if** they operate as room-based inventory (full dorm-bed logic is NOT in scope at launch).

### 2.4 Hotel types explicitly NOT served at launch
- Large chains.
- Hotels above 80 rooms.
- Businesses requiring full multi-property chain management.
- Vacation rentals / Airbnb-style property managers.
- Corporate housing platforms.
- Hostels that require full bed-level inventory logic.

### 2.5 Considered for later, not launch
- Small chains (multi-property under one account). May be re-evaluated post-launch.
- Additional LATAM countries (post-launch; product must avoid AR-only coupling in architecture).

### 2.6 Acquisition channel assumptions
TODO(owner): self-serve web signup vs assisted sales vs partner referral (see §12.6 and §16).

---

## 3. User personas (platform-wide)

### 3.1 Hotel Owner / Co-owner
Subscribes, configures the hotel, invites staff, approves AI-generated drafts, oversees operations. Role observable in code: `owner`, `co_owner`.

### 3.2 Front desk / Operator
Daily operations: reservations, check-in/out, payments, handling OTA conflicts. TODO(verify) role name in code.

### 3.3 Manager (future)
Analytics, pricing/policy review, staff oversight. TODO(owner): in scope at launch? Post-launch?

### 3.4 Platform Admin (us)
Manages tenants, subscriptions, observability, support, cross-tenant issues. TODO(owner): scope of platform-admin capabilities at launch.

---

## 4. Subscription tiers & plan limits

Observable in repo (`app/models/subscription_v2.py`): plans `starter`, `pro`, `ultra`; statuses `active`, `past_due`, `suspended`, `trialing`, `demo`; per-subscription `room_limit`, `staff_limit`, `current_period_end`, `grace_until`.

Shape resolved 2026-04-16 (P-B); revised 2026-04-16 per owner correction (OTAs + MP + PayPal available to all tiers; Stripe gates `pro`/`ultra`). Concrete values (numeric limits, prices) deferred.

### 4.1 Common capabilities (available to ALL tiers)

These do NOT differentiate tiers. Every paid tier and the trial include:

- **Manual reservation loading** (operator creates a reservation directly).
- **Booking (OTA) integration** — inbound at launch.
- **Expedia (OTA) integration** — inbound at launch.
- **MercadoPago** payment gateway.
- **PayPal** payment gateway.
- Core platform functionality (reservations, rooms, guests, check-in/out, basic reports, onboarding wizard, security, audit).

Note on Despegar: an adapter exists in code (`app/services/ota/adapters/despegar.py`). TODO(owner) confirm whether Despegar is part of the launch catalogue alongside Booking + Expedia.

### 4.2 Tier differentiation (shape)

Direction is low → medium → high. Numeric values deferred.

| Dimension | starter | pro | ultra |
|---|---|---|---|
| Positioning | Entry — smallest hotels getting started | Mainstream — full operating team | Top — max of target segment, most flexibility |
| `room_limit` | Low (covers 1-room properties upward) — TODO(owner) exact | Medium — TODO(owner) exact | High; up to segment max of 80 — TODO(owner) exact |
| `staff_limit` | Few users | Full operating team | Larger team / more flexibility |
| **Stripe** (card payments, international) | ❌ not included | ✅ included | ✅ included |
| AI / Gemma depth | Onboarding/config help + simple assistance | Operational recommendations + limited advisory | Full AI: deeper analysis + advanced assistance |
| Reports depth | Basic | Operational + commercial | Advanced, exportable, deeper analysis |
| Support level | Standard | Priority | Closest / highest priority |
| Multi-hotel per account | 1 hotel | 1 hotel | Multiple hotels (post-launch; not a launch priority) |
| Advanced operational capabilities (future) | Limited | Partial | Full — TODO(owner) to define |
| Monthly price | TODO(owner) | TODO(owner) | TODO(owner) |
| Trial path | Enter through one 14-day Pro trial per hotel | Trial tier | No direct trial; checkout required |

Not tier-differentiated: OTAs, MercadoPago, PayPal, manual reservation loading (all included everywhere — see §4.1).

### 4.3 Trial
- **Trial enabled.** Duration: **14 days**.
- Trial runs on the main product with reasonable limits — **no separate implementation** distinct from the standard tiers.
- The trial grants `pro`, starts from the onboarding flow, and is available once per hotel. A durable `trial_started` event prevents a second trial if subscription plan state later changes.
- TODO(owner): post-trial transition behavior (downgrade to `starter` paid? suspend? churn?). Until checkout and payment confirmation exist, no paid plan may be activated from hotel self-service or the manual plan endpoint.

### 4.4 Free forever
- **No free-forever tier.** `starter` is paid from day one.

### 4.5 Demo status
- The `demo` subscription status exists for commercial demos, prospect setups, and internal validation.
- **Not a public commercial plan.** Sales / platform-admin tool only.
- TODO(owner): who may create `demo` subscriptions (platform admin only? assisted sales only?) and data-lifecycle rules (auto-reset? conversion to real plan?).

### 4.6 Internal / platform-admin exceptions (owner-hotel access)

For the owner's own hotel (and any internally comped cases):
- **Not** modeled as a public "free largest plan" coupon.
- Modeled as an **internal comped subscription** or **platform-admin override** — a subscription that bypasses the public pricing rules but still uses the same `Subscription` record structure with a dedicated marker/reason.
- One-time public coupons are a possible commercial mechanism and may be added later, but the product default for owner/internal access is the administrative override, not a public discount.
- TODO(architect): design the admin-override mechanism (e.g. a `comped` flag + audit reason + expiry) as a distinct concept from public `trialing` / `demo`.
- TODO(owner): confirm whether any staff of the platform company get the same comp treatment on their personal hotels.

### 4.7 Enforcement
- Global toggle `SUBSCRIPTION_ENFORCEMENT` is off by default in code.
- TODO(owner): when to flip it on, and whether any tier should be exempt from enforcement at launch.

### 4.8 Open items
- Exact numeric `room_limit` / `staff_limit` per tier.
- Confirm Despegar inclusion in the launch common-OTA set (§4.1).
- Concrete monthly prices per tier (the app must show “Precio a definir” until approved).
- Post-trial behavior.
- Upgrade / downgrade rules (prorated? immediate? end-of-period?).
- Definition of the "advanced operational capabilities" differentiator for `ultra`.
- Admin-override / comped subscription mechanism (§4.6) — architect design.

---

## 5. Platform scope by module

For each module, state what the **platform** provides and what each **hotel** configures.

| Module | Platform provides | Hotel configures |
|---|---|---|
| Reservations | Data model, lifecycle, audit | Reservation types enabled, duration-based deposit rules, cancellation rules |
| Rooms & categories | Structure, state machine | Their rooms, categories, capacities, base tariffs |
| Guests | PII fields, companions | — (no platform-level config) |
| Check-in / out | Flow + audit | Required legal fields (per jurisdiction, TODO) |
| Payments | Platform-wide: MercadoPago + PayPal (all tiers) + cash/transfer/manual. Stripe available on `pro`/`ultra` only. Card-brand support follows whatever Stripe supports for that merchant + geography — not modeled as separate product integrations. Positive payments below the outstanding balance are valid partials; the remainder stays due. | Which of the enabled methods to turn on + own gateway credentials; exchange market, buy/sell side, and foreign-tender rounding policy (`round_up`, `round_down`, `nearest_ten`, `exact`, or `keep_remainder`). `exact` uses the converted tender amount to cent precision and settles the displayed balance; the default `keep_remainder` leaves any residual available to collect in another currency. Rounding applies when the tender and reservation currencies differ; same-currency payments keep the entered amount. Any excess created by a rounding-up policy is a reservation-scoped credit in the tender currency, separate from the amount paid and revenue. Its manual cash refund requires `payment:refund` (Owner, Co-owner, and Manager by default); credit cannot currently be applied to another reservation. |
| OTA inbound | Booking / Expedia / Despegar adapters | Which channels connected + credentials |
| OTA outbound | Future (post-launch) | TODO(owner) |
| Allocation engine | Automatically assign/rearrange eligible future reservations when the complete plan is safe; reduce room-level gaps; never move a reservation after any guest checks in; allow a person to approve a locked move once while keeping its lock | Room/category/channel/company priorities and operational preferences within platform safety bounds |
| Experimental pricing advice | Daily and configured high-demand-date recommendations with an exact category/night price; save as a reviewable tariff draft | Comparable season labels, event dates and per-hotel pilot thresholds; a person with permission approves every change |
| Gemma / AI | Orchestrator, guardrails, draft/apply | Opt-in features per tier, feedback retention |
| Reports | Report catalogue | Filters, saved views (TODO) |
| Onboarding | AI-assisted wizard | Their hotel profile |
| Settings | UI surface | Hotel, Users, Connections, Security, Subscription, Assistant, Tests |
| Multi-hotel | Membership + invitations | Staff roster, roles |
| Subscriptions | Billing, enforcement | Plan choice, payment method |

TODO(owner) refine row by row where more detail is needed.

---

## 6. Configurable vs non-configurable platform behavior

### 6.1 Configurable per hotel (within platform bounds)
- Hotel identity (name, timezone, currency, languages).
- Room inventory, categories, base tariffs.
- Accepted payment methods (from platform catalogue).
- OTA channels connected (from platform catalogue).
- Deposit % and cancellation policy (within tier bounds).
- Allocation policy weights (drafted; applied by owner after review).
- High-demand dates for experimental tariff advice; suggested prices remain drafts until approved.
- AI feature opt-ins (within tier).
- Check-in legal fields (from platform catalogue).
- Staff roster + role assignment.
- Gmail/SMTP sender (per hotel).

### 6.2 Non-configurable (platform-wide)
- Data model and state machines.
- Multi-tenant isolation rules.
- AI guardrails (draft/apply separation, rate limits, no silent mutation).
- Auth model (JWT, bcrypt, rate limits).
- Audit trail requirements.
- Production security validator (`validate_runtime_security`).
- Integration catalogue (which OTAs/gateways are supported).
- Subscription plan structure (tiers themselves; not their limits).

### 6.3 Configurable per platform operator (us)
TODO(owner): which of the above (6.1/6.2) can be adjusted by platform admin on behalf of a tenant.

---

## 7. AI-assisted onboarding & configuration

The product includes an AI assistant (Gemma) that walks each new hotel through setup and ongoing configuration.

### 7.1 Onboarding assistant responsibilities
TODO(owner) confirm scope. Candidate list:
- Interview the owner to fill the hotel profile.
- Draft initial categories, rooms, tariffs from owner input.
- Draft initial allocation policy.
- Draft initial deposit / cancellation policy within platform bounds.
- Suggest which channels to enable.
- Generate an onboarding checklist the owner approves.

### 7.2 Ongoing configuration assistant
- Suggests policy adjustments based on operational data.
- Captures operator feedback on overrides (room moves, reject, rebook).
- Drafts changes; owner applies.

### 7.3 Hard limits on the assistant
Per [AGENTS.md](../AGENTS.md) §21:
- Never auto-applies policy.
- Never mutates source-of-truth booking/guest/payment data.
- Never bypasses authorization.
- Never exposes PII across tenants.
- Every suggestion traceable.

### 7.4 Runtime decision (platform-wide)
TODO(owner): hosted OpenAI-compatible endpoint vs local model per deployment. Per-tier AI feature exposure TODO(owner).

---

## 8. Business rules & policy bounds

- 8.1 Deposit / cancellation — the hotel configures ordered stay-duration bands. Each band requires either a percentage of the reservation total or a number of nights; a deposit is not permission to check in. Individual/direct reservations require the full balance before check-in. Deferred company billing is controlled by the company account setting.
- 8.2 Overbooking — platform stance (allow / forbid / flag). TODO(owner).
- 8.3 Room-move authority — platform rule (owner only / front desk with log / any). TODO(owner).
- 8.4 Manual-review triggers — platform-fixed list; not tenant-tunable. TODO(owner) confirm.
- 8.5 Refund authority — resolved for the pilot by [ADR: Check-in, manual payments, and financial approvals](decisions/checkin-manual-payments-financial-approvals-adr.md): refunds require `payment:refund` and fresh step-up MFA; Owner, Co-owner, and Manager receive it by default. The current manual refund path returns cash only; gateway-backed refunds remain a separate product capability.
- 8.6 Roles & permissions — platform-wide matrix. Observable: `owner`, `co_owner`. TODO(verify) full matrix from `app/dependencies/auth.py`.

### 8.7 Refund handling

Refunds are a platform-wide business rule area, **independent of subscription tiers**. The current pilot supports manual cash refunds of completed reservation payments and reservation-scoped rounding credits. Gateway refunds and reusable vouchers remain future capabilities:

1. **Manual cash refund** — requires `payment:refund`, the original transaction, a reason, and an audit record. A rounding credit is refunded as its own ledger component and cannot exceed the open credit from that source payment.
2. **Monetary refund via original payment gateway** — future capability. When implemented, the amount should be returned through the same channel (MP, PayPal, Stripe where enabled), idempotently and reconciled against the original transaction.
3. **Reusable hotel voucher / credit** — future capability. The rounding credit implemented for this pilot is tied to its reservation and cannot be applied to another stay. Voucher expiry, partial redemption, and transferability require an owner decision.

Rules:
- Manual refund outcome produces an audit record (who / when / amount / path / reason).
- Partial manual refunds are capped by the remaining refundable principal or rounding credit.
- AI / Gemma never issues refunds directly — drafts and reconciliations only (per §9).
- Gateway-specific limits (MP refund windows, PayPal dispute timing, Stripe charge age) are documented per integration — TODO(architect).

TODO(owner):
- Eligibility rules (window, deposits vs post-check-in, non-refundable products).
- Voucher rules (expiry, partial redemption, transferability).
- Whether hotels can customize the three-path order of preference or platform enforces gateway-first.

### 8.8 Confirmed hotel operating rules (2026-10-15)

- A hotel can combine deposit bands, for example 30% for a one-night stay and one night's value for longer stays. Pricing uses the applicable dated nightly prices when available; explicit negotiated totals without a nightly breakdown use an even per-night allocation.
- Direct/non-deferred reservations cannot check in until the full reservation amount is paid. The deposit secures the reservation only.
- A company configured for deferred billing can check in and check out with an outstanding balance. Reserved nights and actually used nights are recorded separately; the hotel's company settlement and decision to bill reserved or used nights remain manual.
- Extensions are available to direct and company reservations. Direct extensions may leave the additional amount outstanding. Deferred company extensions are recorded to the company account.
- A physical move of a company guest from a double to a triple room preserves the contracted category and base tariff; a configured extra-person/night charge is tracked separately. Individual room/category re-pricing follows the selected operational rule.
- `reservation:read` may read the reservation balance and payment history. Registering payments, refunds, or cash movements remains protected by their action permissions.

### 8.9 Individual guest arrivals (2026-10-25)

- Check-in is recorded separately for each guest in a reservation, with the arrival time and acting user/role. A repeated request for the same guest returns the original arrival record and does not create a duplicate or change the reservation balance or payments.
- The first guest can arrive only when the assigned room passes the existing ready-room gate; that arrival marks the physical room occupied. Later guests are recorded against that occupied room.
- Each hotel configures the reservation status policy: keep `partial_checkin` until the party arrives (default), or mark `checked_in` when its first guest arrives. The selected policy is snapshotted on the reservation when the first arrival is recorded. Missing guest profiles remain visible and do not count as arrivals.

---

## 9. AI product boundaries (platform-wide)

Allowed (observable): insights, drafts of allocation policy, onboarding assistant, chat, feedback capture.
Forbidden (hard lines per AGENTS.md §21): silent policy application, mutation of business data, auth bypass, PII cross-tenant leak, unaudited actions.
The experimental tariff engine is advisory; it can prepare an exact rate-change draft but cannot approve or apply it.
Per-tier exposure: TODO(owner).
Feedback retention: TODO(owner).

---

## 10. Security & compliance baseline (platform-wide)

Full detail in [security-baseline.md](security-baseline.md). Platform-level commitments:
- Multi-tenant isolation enforced at `hotel_id`.
- JWT + bcrypt + login rate limit.
- Fernet-encrypted integration secrets.
- Production fail-closed validator for secrets, URLs, webhook secrets.
- Webhook signature verification (MP today; more TODO(owner)).
- No PAN/CVV storage — gateway tokens only (TODO(verify)).
- PII handling scope: TODO(owner).
- Jurisdictions supported at launch: **Argentina only** (resolved via P-A). Legal check-in fields for AR: TODO(owner) — see §7.2.

---

## 11. Integrations (platform catalogue)

Resolved (partial) 2026-04-16 via P-B revision. Tier exposure in §4.

- **OTA — available to all tiers**: Booking (inbound), Expedia (inbound). Despegar (adapter exists in code) — TODO(owner) confirm launch inclusion. OTA outbound remains post-launch.
- **Payments — available to all tiers**: MercadoPago, PayPal, cash, bank transfer, other manual methods.
- **Payments — `pro` / `ultra` only**: Stripe (card processing). Card brands (Visa / Mastercard / Amex / Discover / etc.) are whatever the Stripe merchant account supports for the hotel's geography — **not** modeled as separate product integrations.
- **Email**: Gmail OAuth per hotel, plus owner-managed system mail for auth and transaccional system flows.
- **Future**: channel manager, accounting export, housekeeping app.

Notes:
- Stripe SDK / adapter is NOT yet in the repo (no `stripe` package in `requirements.txt`, no Stripe adapter). TODO(architect): scope Stripe integration addition.
- Per-hotel enablement and credentials: [hotel-onboarding-data.md](hotel-onboarding-data.md).

---

## 12. Operational model (platform-wide)

- 12.1 Environments: local / staging / production. TODO(owner) target infra.
- 12.2 Backups & retention: TODO(owner).
- 12.3 Observability: TODO(owner) — minimum signals.
- 12.4 Support model & SLA per tier: TODO(owner).
- 12.5 Incident response & escalation: TODO(owner).
- 12.6 Tenant provisioning: self-serve via `RegisterOwnerPage` today; TODO(owner) confirm self-serve vs assisted-only at launch.
- 12.7 Tenant off-boarding & data export: TODO(owner).

---

## 13. Success metrics

### 13.1 Product KPIs (post-launch)
TODO(owner). Candidates: MRR, active hotels, hotels >1 month retained, % hotels using AI, OTA connection success rate, time-to-first-reservation after signup.

### 13.2 First-customer pilot KPIs
TODO(owner). Candidates: % OTA reservations needing manual intervention, check-in time, solver override rate, Gemma acceptance rate, P0 incidents.

### 13.3 Public-release gate
Hard gate per master plan §"Go-live review". TODO(owner) approve/extend.

---

## 14. Commercial model

- 14.1 Pricing: TODO(owner) per tier (see §4).
- 14.2 Billing: TODO(owner) — which gateway processes subscription payments (MP? Stripe? manual?).
- 14.3 Trial / free tier: TODO(owner).
- 14.4 Contract / SLA: TODO(owner).
- 14.5 Discounting / promotions: TODO(owner).
- 14.6 Tax handling (AR IVA, etc.): TODO(owner).

---

## 15. Branding & distribution

- 15.1 Product name (public): TODO(owner).
- 15.2 Domain(s): TODO(owner).
- 15.3 Marketing site: TODO(owner) — in scope at launch?
- 15.4 Languages supported at launch: **Spanish only** (resolved via P-A). Architecture must stay i18n-ready for Spanish-speaking LATAM expansion later.
- 15.5 Accessibility targets: TODO(owner).

---

## 16. Pilot strategy (first real customer)

The pilot is **one real hotel using the SaaS product**, not a bespoke build.

- 16.1 Pilot-customer selection: TODO(owner).
- 16.2 Pilot commercial terms (free / discounted / paid): TODO(owner).
- 16.3 Assistance level (white-glove vs self-serve with support): TODO(owner).
- 16.4 Feedback loop into product backlog: use [roadmap.md](roadmap.md) and master plan Fase C.
- 16.5 Exit criteria: pilot success = KPIs (13.2) green AND no P0 open.

Per-hotel profile of the pilot customer lives in [hotel-onboarding-data.md](hotel-onboarding-data.md), not here.

---

## 17. Risks & open questions

Rolling list. Each: risk | decision owner | status.
- TODO(owner): seed from [architecture-audit.md](architecture-audit.md) §5.

---

## 18. Glossary

Platform terms:
- **Tenant / hotel** — one subscribed hotel, isolated by `hotel_id`.
- **Plan** — subscription tier (`starter`, `pro`, `ultra`).
- **Subscription status** — `active`, `past_due`, `suspended`, `trialing`, `demo`.
- **Platform catalogue** — set of integrations/payment methods/AI features the platform supports (a superset of what any single hotel enables).
- **hotel_id scoping** — tenancy boundary for every domain record.
- **manual_review** — allocation/OTA state flagged for human resolution.
- **rebook OTA → direct** — operator converts an OTA reservation into a direct one.
- **locked** — reservation/room state the solver must not move.
- **settlement** / **settlement hints** — financial reconciliation metadata.
- **fragmentation / gap day** — allocation penalty target (1-night gaps).
- **draft / apply** — AI proposes; authorized human applies.
- **runtime-status** — health of the Gemma inference backend.
- **pending_actions** — follow-ups generated when auto-resolution is unsafe.
- **allocation_status** — per-reservation placement state.
- **SUBSCRIPTION_ENFORCEMENT** — global toggle; when off, writes stay allowed regardless of plan.
- TODO(owner) extend with additional domain terms.

---

## 19. Change log

| Date | Author | Change |
|------|--------|--------|
| 2026-04-16 | architect | Initial scaffold (assumed single-hotel framing). |
| 2026-04-16 | architect | Reframed as multi-tenant SaaS product; split per-hotel data into [hotel-onboarding-data.md](hotel-onboarding-data.md). |
| 2026-04-16 | owner | P-A answered: AR launch, Spanish, ARS, 6–80 rooms, independent/boutique/apart-hotel/room-based hostel. |
| 2026-04-16 | owner | P-B answered: tier shape (low/mid/high per dimension), 14-day trial, no free-forever, demo status for sales/internal only, prices deferred. |
| 2026-04-16 | owner | P-A revision: platform supports 1–80 rooms (primary commercial target stays small-to-mid). |
| 2026-04-16 | owner | P-B revision: OTAs + MP + PayPal + manual reservation are common to all tiers. Stripe gates `pro`/`ultra`. Card brands handled via Stripe, not modeled as separate integrations. Owner-hotel access = internal comped subscription / admin override, not public coupon. Refund handling moved out of tier differentiation into §8.7 with three paths (gateway / voucher / manual). |
| 2026-10-15 | owner + Codex | Confirmed configurable deposit bands, full-payment direct check-in, deferred-company settlement, reserved/used nights, extension balances and company physical-room pricing rules; see §8.8 and TECH-0150–TECH-0152. |
| 2026-10-15 | Codex | Added local remediation backlog for analytics query budgets, export resource bounds, atomic AI quotas, no-show rounding and trial/comped transitions; see TECH-0153–TECH-0157. No-show, export range and subscription-expiry semantics remain owner decisions. |
| 2026-10-15 | Codex | Applied two query-shape fixes: one-capability guards use selective fresh permission reads, and guest list/search no longer hydrates unused reservations/tags; see TECH-0158–TECH-0159. |
| 2026-10-18 | Owner + Codex | Exportaciones conservan el rango histórico completo sin corte por antigüedad. Se aplicaron consultas frontend diferidas/agrupadas para búsqueda global, tarifas, lavandería móvil y recuperación entre pestañas; TECH-0154 y TECH-0160–TECH-0162 documentan límites pendientes y aceptación. |
| 2026-10-27 | Owner + Codex | Separa la autoasignación segura de reservas futuras del asesor experimental de tarifas. El hotel marca temporadas comparables y eventos de alta demanda; el piloto usa ocupación 80/40, pickup ±20% y un paso máximo configurable de 5%. La demanda define la dirección y la brecha frente al promedio USD comparable modula el porcentaje aplicado a la tarifa actual. Las tarifas publicadas se comparan con FX verificable; cada sugerencia queda en borrador hasta la aprobación humana. Véase TECH-0062 y TECH-0064. |
| TODO(owner) | | |
