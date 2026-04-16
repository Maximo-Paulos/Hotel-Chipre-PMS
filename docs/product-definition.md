# Product Definition — Hotel Chipre PMS (SaaS Platform)

> Product-level contract for the **multi-tenant SaaS PMS** we are building and selling.
> This is NOT a single-hotel profile. Each subscribed hotel configures itself inside the product — see [hotel-onboarding-data.md](hotel-onboarding-data.md).
> Related: [roadmap.md](roadmap.md), [architecture-audit.md](architecture-audit.md), [security-baseline.md](security-baseline.md), [master-plan-pilot-to-public.md](master-plan-pilot-to-public.md).

---

## 1. Purpose & non-goals

### 1.1 What this product is
A multi-tenant SaaS Property Management System for hotels, covering reservations, rooms, guests, check-in/out, payments, OTA integration, and AI-assisted operations. Each subscribed hotel runs in isolated tenant scope (`hotel_id`) on a shared platform.

### 1.2 What it is NOT (platform-level non-goals)
TODO(owner) confirm/extend. Default non-goals unless owner says otherwise: full accounting, marketing automation, CRM campaigns, public booking-engine for the hotel website, housekeeping mobile app, revenue-management beyond allocation advice, on-prem/self-hosted deployment model.

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
| Trial available? | Yes (see §4.3) | Yes (see §4.3) | Yes (see §4.3) |

Not tier-differentiated: OTAs, MercadoPago, PayPal, manual reservation loading (all included everywhere — see §4.1).

### 4.3 Trial
- **Trial enabled.** Duration: **14 days**.
- Trial runs on the main product with reasonable limits — **no separate implementation** distinct from the standard tiers.
- TODO(owner): which tier the trial grants access to (default assumption: full `pro` for 14 days) and post-trial transition behavior (downgrade to `starter` paid? suspend? churn?).

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
- Concrete monthly prices per tier.
- Trial grant tier + post-trial behavior.
- Upgrade / downgrade rules (prorated? immediate? end-of-period?).
- Definition of the "advanced operational capabilities" differentiator for `ultra`.
- Admin-override / comped subscription mechanism (§4.6) — architect design.

---

## 5. Platform scope by module

For each module, state what the **platform** provides and what each **hotel** configures.

| Module | Platform provides | Hotel configures |
|---|---|---|
| Reservations | Data model, lifecycle, audit | Reservation types enabled, deposit %, cancellation rules |
| Rooms & categories | Structure, state machine | Their rooms, categories, capacities, base tariffs |
| Guests | PII fields, companions | — (no platform-level config) |
| Check-in / out | Flow + audit | Required legal fields (per jurisdiction, TODO) |
| Payments | Platform-wide: MercadoPago + PayPal (all tiers) + cash/transfer/manual. Stripe available on `pro`/`ultra` only. Card-brand support follows whatever Stripe supports for that merchant + geography — not modeled as separate product integrations. | Which of the enabled methods to turn on + own gateway credentials |
| OTA inbound | Booking / Expedia / Despegar adapters | Which channels connected + credentials |
| OTA outbound | Future (post-launch) | TODO(owner) |
| Allocation engine | OR-Tools solver, draft/apply policy | Policy weights within allowed bounds |
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

- 8.1 Deposit / cancellation — platform enforces bounds (min/max %); hotel chooses within. TODO(owner) bounds.
- 8.2 Overbooking — platform stance (allow / forbid / flag). TODO(owner).
- 8.3 Room-move authority — platform rule (owner only / front desk with log / any). TODO(owner).
- 8.4 Manual-review triggers — platform-fixed list; not tenant-tunable. TODO(owner) confirm.
- 8.5 Refund authority — TODO(owner): which role may issue refunds (owner only? co_owner? front desk with cap?). See §8.7 for refund-handling paths.
- 8.6 Roles & permissions — platform-wide matrix. Observable: `owner`, `co_owner`. TODO(verify) full matrix from `app/dependencies/auth.py`.

### 8.7 Refund handling

Refunds are a platform-wide business rule area, **independent of subscription tiers**. At launch the platform must support, at minimum, these three paths:

1. **Monetary refund via original payment gateway** — when the gateway supports it, the amount is returned through the same channel (MP, PayPal, Stripe where enabled). Idempotent, audited, reconciled against the original transaction.
2. **Internal voucher / credit** — when configured by the hotel, the refund is issued as a hotel credit for future use. Voucher lifecycle (expiry, partial redemption, non-transferability) TODO(owner).
3. **Manual review / manual handling** — when gateway constraints, policy, or ambiguity prevent the above two, the case is flagged `manual_review` with an explicit reason. No silent close.

Rules:
- Refund outcome always produces an audit record (who / when / amount / path / reason).
- Partial refunds are allowed if the chosen path supports them; otherwise fall to manual review.
- AI / Gemma never issues refunds directly — drafts and reconciliations only (per §9).
- Gateway-specific limits (MP refund windows, PayPal dispute timing, Stripe charge age) are documented per integration — TODO(architect).

TODO(owner):
- Eligibility rules (window, deposits vs post-check-in, non-refundable products).
- Voucher rules (expiry, partial redemption, transferability).
- Whether hotels can customize the three-path order of preference or platform enforces gateway-first.

---

## 9. AI product boundaries (platform-wide)

Allowed (observable): insights, drafts of allocation policy, onboarding assistant, chat, feedback capture.
Forbidden (hard lines per AGENTS.md §21): silent policy application, mutation of business data, auth bypass, PII cross-tenant leak, unaudited actions.
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
- **Email**: SMTP + Gmail OAuth per hotel.
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
| TODO(owner) | | |
