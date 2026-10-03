# ADR: Check-in, manual payments, and financial approvals

- Status: accepted for the pilot
- Date: 2026-09-27
- Product input: Claude's second end-to-end operations review, applied at the owner's request

## Context

The review found that the current full-prepayment check-in rule does not match a small hotel's deposit-and-settle-at-checkout workflow; in-person card/debit payments could remain pending; and a receptionist could refund completed cash payments and cancel a paid reservation without a second control. It also found that check-in did not compare the hotel-local arrival date.

## Decisions

1. Each hotel has a `checkin_payment_policy`: `deposit` (default), `total`, or `free`. `free` means no payment is required before check-in; it does not waive the reservation balance. Checkout continues to enforce the operational balance, including stay charges and consumption. This deliberately changes existing hotels to the pilot default during migration; it is not a behavior-preserving default change.
2. Check-in is allowed only on/after the arrival date and before the departure date in the hotel's time zone. Early arrival and stale reservations after checkout are rejected until the product defines how to extend occupied inventory, reprice the stay, and recheck all overlapping reservations atomically. A manager-only bypass without those rules could create an overbooking or an unbilled night.
3. In-person card, debit, and directly verified bank-transfer payments may complete immediately only with a card coupon or transfer-operation reference. The authenticated staff user remains the transaction actor. Uploaded transfer proofs continue through their separate review-and-approval workflow.
   The normalized reference is unique per hotel and payment method. If different terminals or banks can issue the same number, staff include that source in the entered identifier (for example, terminal/bank plus operation number).
4. `payment:refund` is separate from ordinary payment/cash operation and requires action-bound step-up MFA. The pilot default grants it to owner and manager, not reception. The current manual refund path returns cash only; this change does not implement gateway refunds.
   A refund must point to a completed original payment for the same hotel and reservation, include a short reason, and remain within that original payment's unrefunded balance. The reason is returned to the authorized refund operator but omitted from the general financial summary.
5. Cancelling a reservation with completed payment history requires `reservation:cancel_paid` plus fresh step-up MFA. Owner and manager receive it by default. Cancellation does not issue an automatic refund.
6. Physical receipt of custody and approval of a cash-close difference remain independent permissions.
7. Manual cash expenses are separate from ordinary cash-session operation. Owner, co-owner, and manager can record expenses by default; Reception can record only when `cash:expense` is explicitly granted. Recording creates a pending expense with category, vendor, and receipt reference or private image; it does not change the drawer balance. Owner, co-owner, or manager must approve or reject it, and every decision requires action-bound step-up MFA. Approval creates exactly one cash movement in the same transaction as the expense status and audit event. Guest refunds continue through `payment:refund`, which creates the linked cash outflow itself.

## Consequences

- Existing hotels intentionally migrate to the `deposit` check-in rule; operators must be told that prior full-payment behavior changes.
- Transactions gain a nullable manual reference; existing gateway, cash, and approved-proof transactions remain readable.
- Refunds are explicitly traceable and capped per source payment; PostgreSQL enforces tenant-consistent lineage. SQLite migration tests skip this self-FK because its batch-table rebuild cannot safely recreate a self-reference with foreign-key enforcement enabled; SQLite test schemas are built from ORM metadata and retain the constraint.
- Staff can record a completed card/debit payment and its audit reference without falsely treating it as physical cash.
- The cashier workflow remains able to collect the remainder at checkout, where the existing outstanding-balance gate still applies.
- Hotels can select stricter total-payment check-in or no-upfront-payment check-in from their configuration.

## Verification and release boundary

The change is covered by service/API tests for the three check-in policies, arrival/departure guards, manual-payment references, refund permission and step-up, and paid-reservation cancellation. Local SQLite tests are not proof of a production migration or cloud journey. Before applying the migration to the live database, take a recoverable backup using the authorized free-tier path, test the migration against a disposable copy, then run authenticated role-based cloud QA and verify the deployed commit. Downgrading after the new settings/references are used drops those values; restore from backup instead of assuming downgrade is data-preserving.
