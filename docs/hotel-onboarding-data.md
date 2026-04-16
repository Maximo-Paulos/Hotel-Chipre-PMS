# Hotel Onboarding Data Model

> Defines the **per-hotel** data each subscribed hotel provides during onboarding and can (or cannot) change afterward.
> This is the counterpart to [product-definition.md](product-definition.md): that doc is the platform contract, this one is the tenant-side configuration shape.
> Observable surfaces: `app/api/onboarding.py`, `app/services/onboarding_service.py`, `app/schemas/onboarding.py`, `frontend/src/views/onboarding/OnboardingWizard.tsx`.

---

## 1. Principles

1. Hotels configure themselves inside the product — guided by an AI assistant and a wizard UI.
2. All configuration is scoped by `hotel_id`.
3. Required fields block go-live for that hotel; optional fields can be filled later.
4. Some fields are mutable for life; some are immutable after first use (e.g. currency, once transactions exist).
5. Platform rules (non-configurable) are authoritative; hotel config operates within their bounds (see [product-definition.md](product-definition.md) §6).

## 2. Onboarding steps (platform-provided, AI-assisted)

Observable flow from `app/api/onboarding.py`:
1. **Owner contact** — name, email, phone, role. (`POST /api/onboarding/owner`)
2. **Room categories** — code, name, base price per night, max occupancy. (`POST /api/onboarding/categories`)
3. **Rooms** — room number, floor, `category_code`. (`POST /api/onboarding/rooms`)
4. **Staff roster** — name, role, email. (`POST /api/onboarding/staff`)
5. **Finish** — marks onboarding complete. (`POST /api/onboarding/finish`)

TODO(owner) confirm additional steps the AI assistant should walk the hotel through:
- Hotel identity (name, location, timezone, currency, languages).
- Deposit / cancellation policy (within platform bounds).
- Payment methods to enable + gateway credentials.
- OTA channels to connect + credentials.
- Email sender (SMTP or Gmail OAuth).
- Legal check-in fields (per jurisdiction).
- Allocation policy draft review & approval.
- Subscription plan choice & billing.

## 3. Per-hotel data inventory

### 3.1 Identity (required)
- Hotel name.
- Country + city + address. TODO(verify) fields in `hotel_config`.
- Timezone (default `America/Argentina/Buenos_Aires` per `app/config.py`).
- Primary currency.
- Operating languages.

### 3.2 Inventory (required)
- Room categories (code, name, max occupancy, base price).
- Rooms (number, floor, category).
- Floors / property layout notes (optional).

### 3.3 People (required)
- Owner / co-owner.
- Staff roster with roles.
- Invited users via invitation flow (`app/api/invitations.py`).

### 3.4 Policies (required, within platform bounds)
- Default deposit % (platform default: `DEFAULT_DEPOSIT_PERCENT=30.0`).
- Cancellation policy.
- Overbooking stance (if platform allows per-tenant choice — TODO(owner)).
- Room-move authority mapping to local roles (within platform rule).

### 3.5 Channels & payments (optional, per hotel)
- OTA channels enabled: Booking, Expedia, Despegar — plus per-channel credentials.
- Payment methods enabled: MercadoPago, PayPal, cash, bank_transfer, card.
- Per-gateway credentials (stored encrypted via Fernet).
- Webhook endpoints automatically provisioned per tenant.

### 3.6 Communications (optional)
- Email sender: platform SMTP by default, Gmail OAuth per hotel.
- Transactional templates: TODO(owner) — hotel-editable or platform-wide?

### 3.7 AI configuration (optional, subject to tier)
- Gemma opt-in per feature (insights, drafts, chat).
- Feedback-capture preferences.
- Allocation policy draft acceptance workflow (which user role applies).

### 3.8 Legal / compliance (required, jurisdiction-dependent)
- Check-in legal fields: doc type, nationality, minors handling, fiscal registry. TODO(owner) per supported jurisdiction.
- Data retention preferences (if tenant-configurable). TODO(owner).

### 3.9 Subscription (required)
- Plan (`starter` / `pro` / `ultra`).
- Billing contact + payment method.
- Status transitions handled by platform.

## 4. Mutability

| Field | Mutable after go-live? | Notes |
|---|---|---|
| Hotel name, address, phone, email | yes | Audit the change |
| Timezone | TODO(owner) | Changing post-transactions is risky |
| Currency | TODO(owner) | Likely immutable once payments exist |
| Languages | yes | |
| Categories (code) | no (once used) | TODO(verify) enforcement |
| Categories (name, price, capacity) | yes | |
| Rooms | yes | Closing a room with future reservations requires manual review |
| Staff roster | yes | Role changes audited |
| Deposit / cancellation policy | yes | Within platform bounds |
| Payment methods | yes | Disabling an active method flagged |
| OTA credentials | yes | Re-auth as needed |
| Plan | yes | Up/downgrade rules per commercial model — TODO(owner) |
| Legal check-in fields schema | platform-managed | Hotel can only fill values |

TODO(owner) finalize every `yes/no` decision and enforcement strategy.

## 5. Data the AI assistant collects but does NOT own

The AI onboarding assistant asks questions and **drafts** values; the hotel owner confirms them before they become configuration. The AI never:
- Sets credentials silently.
- Applies policies without owner approval.
- Writes to other tenants.
- Bypasses platform bounds.

Per-hotel feedback captured during operation feeds the assistant's future drafts for **that hotel only** unless explicitly anonymized and opted-in for platform-wide learning. TODO(owner) confirm cross-tenant learning stance.

## 6. Onboarding completion criteria

Platform considers a hotel onboarded when:
- Owner contact saved.
- At least one category and one room exist.
- At least one staff member (front desk) on roster.
- Active subscription (including `trialing` / `demo`).
- Onboarding `finish` called.

TODO(owner) extend: require a payment method, an OTA connection, or a legal-fields completeness check before enabling production mode?

## 7. References

- Observable code: `app/api/onboarding.py`, `app/services/onboarding_service.py`, `app/schemas/onboarding.py`, `frontend/src/views/onboarding/OnboardingWizard.tsx`.
- Models: `app/models/hotel_config.py`, `app/models/hotel_membership.py`, `app/models/subscription_v2.py`.
- Platform contract: [product-definition.md](product-definition.md).
