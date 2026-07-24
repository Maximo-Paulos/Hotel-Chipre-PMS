# Transactions vs Payments: Source-of-Truth Rule

**Date:** 2026-06-12  
**Status:** Authoritative — resolves worktree/main divergence  
**Scope:** Financial data layer convergence

---

## The two tables

### `transactions` (canonical financial ledger)
- **Source of truth for: amount_paid, balance_due, arqueo**
- One row per payment event in the financial sense
- Written by `payment_service.py` after any money movement
- Used by the financial ledger read helpers, `CashCloseReport.expected_balance`, and new financial reports
- `amount`, `payment_method`, `status`, `type` are the core columns
- Always `Numeric(12, 2)` — never `Float`

### `payments` (gateway tracking record)
- **Source of truth for: provider state, external_payment_id, webhook lifecycle**
- One row per gateway payment object (MercadoPago preference, PayPal order, Stripe intent)
- Written when a payment gateway object is created (before money arrives)
- Tracks provider-specific state: `external_payment_id`, `external_status`, `gateway_response`
- When a payment transitions to `completed`: writes a `Transaction`

### `payment_links` (pre-payment guest-facing object)
- **Source of truth for: link lifecycle, QR/checkout URL, recipient contact**
- Sent to guest before payment; may collect multiple partial payments
- When a PaymentLink receives a webhook: creates/updates a `Payment`, which then creates a `Transaction`

### Manual bank-transfer proof

Bank transfer is deliberately two-phase:

1. Reception uploads a JPEG, PNG or WEBP proof. The image is validated, hashed
   and stored under a generated private key; only metadata is persisted in
   `payment_proofs` with status `pending`.
2. An owner, co-owner or manager explicitly approves or rejects it. Approval
   calls the same canonical `process_payment` ledger path with an idempotency
   key (`transfer-proof:{proof_id}`), creates a completed `Transaction`, and
   refreshes the materialized `reservation.amount_paid` cache. Rejection never changes the balance.

The image is served only through an authenticated endpoint. It is never put in
the public static bundle, logs, transaction description, or an analytics store.

---

## Data flow

```
Hotel staff creates payment link
    → PaymentLink (status=active)

Guest pays via MercadoPago/PayPal/Stripe
    → Webhook received → payment_webhook_events (raw log)
    → Payment updated (status=completed, external_payment_id set)
    → Transaction inserted (type=payment, status=confirmed)
    → reservation.amount_paid refreshed (via Transaction aggregate)

Hotel staff records cash payment directly
    → Transaction inserted directly (type=payment, payment_method=cash)
    → active CashSession is reused, or a zero-opening session is created automatically
    → CashMovement linked to the Transaction (income/refund expense)
    → NO Payment or PaymentLink needed
    → reservation.amount_paid refreshed
```

---

## What each service writes

| Operation | Table(s) written |
|-----------|-----------------|
| Cash payment recorded at front desk | `transactions` + `cash_movements` + active `cash_sessions` |
| Credit/debit card via POS (no gateway) | `transactions` only |
| Bank transfer submitted | `payment_proofs` metadata + private evidence file; no balance change |
| Bank transfer confirmed | `payment_proofs` + `transactions` + reservation financial state |
| MercadoPago link created | `payment_links` + (later) `payments` + `transactions` |
| PayPal/Stripe checkout created | `payment_links` + (later) `payments` + `transactions` |
| Payment gateway webhook received | `payment_webhook_events` → `payments` → `transactions` |
| Refund issued | `transactions` (type=refund) + optionally `hotel_vouchers` |

---

## Idempotency rule

- `transactions`: idempotent on (`hotel_id`, `reservation_id`, `idempotency_key`)
- `payments`: idempotent on (`hotel_id`, `provider`, `external_payment_id`) — `UNIQUE` constraint
- `payment_links`: idempotent on (`hotel_id`, `provider`, `external_reference`) — `UNIQUE` constraint
- `payment_webhook_events`: idempotent on (`hotel_id`, `provider`, `webhook_id`) — `UNIQUE` constraint

---

## Balance calculation — always from `transactions`

```python
# CORRECT for new reads:
balance_due = reservation.total_amount - sum(t.amount for t in transactions 
                                              if t.status == 'confirmed' and t.type == 'payment')

# WRONG — never use payments.amount as the financial source of truth:
balance_due = reservation.total_amount - sum(p.amount for p in payments
                                              if p.status == 'completed')
```

The `payments` table may have pending/failed records that inflate the apparent total. Only confirmed `transactions` count toward balance.

`Reservation.amount_paid` is retained as a materialized compatibility value for
legacy/imported rows. Once a reservation has transaction rows, application
financial reads and validations use the confirmed transaction aggregate and can
surface a reconciliation gap when the cache differs. Rows that have no ledger
history still need an explicit migration/backfill before provider certification.

---

## Convergence from main branch

Main branch added `payments`, `payment_links`, `payment_webhook_events` via `20260611_payment_core_tables`. This worktree absorbed those tables in `20260612_v72_gaps_phase6_payment_tables`. 

The `transactions` table (from `20260612_audit_log_and_transaction_fk` via `20260410_reservation_financial_lifecycle`) remains the canonical financial ledger. The `payments` table is gateway state only — it never replaces `transactions` for accounting purposes.

**`payment_service.py` is the only layer that writes to both** — it creates a `Payment` when a gateway object is created, and creates a `Transaction` when that payment is confirmed.

---

## What is NOT stored

- Card numbers: never stored anywhere (PCI compliance)
- Full gateway credentials: in env vars only, not in DB
- Payment amounts as `Float`: all monetary columns are `Numeric(12, 2)`
