# Roadmap

This repository is currently in the pilot-to-public transition described in `docs/master-plan-pilot-to-public.md`.

## Current state
- The backend already covers reservations, rooms, payments, onboarding, OTA intake, allocation, auth, subscriptions, and Gemma.
- The frontend already has the public auth flows, onboarding, and protected operational screens.
- The current focus is pilot readiness, not a broad rewrite.

## Current direction
1. Close the operational core for pilot use.
   - OTA inbound lifecycle: new, modified, cancelled, duplicate.
   - Allocation behavior: auto-apply complete, safe reassignments before check-in; preserve explicit locks and request one-time approval for exceptions; measure room-level gaps.
   - Operator UI: room moves, rebook, recalculation, conflict review.
   - Guests and check-in workflows.
2. Harden the pilot.
   - Gemma feedback loop and controlled draft/apply flow.
   - Local Gemma runtime validation.
   - Smoke tests and repeatable QA checks.
3. Prepare public release.
   - Runbook and operator docs.
   - Observability, backup/restore, deployment hardening.
   - Final security/config review.
4. Close the operational and capacity work already in the master development spec.
   - TECH-0064: first local vertical slice is implemented: comparable season/event tags, USD publication history, configurable pilot thresholds and daily/operator-created review drafts. Pure policy tests, docs baseline, frontend typecheck and production build pass; PostgreSQL migration/integration validation, cloud QA and backtest remain release gates.
   - TECH-0150: duration-based deposit rules and full-payment check-in gate.
   - TECH-0151: reserved versus used nights with manual company settlement.
   - TECH-0152: pending-balance extensions, company account handling and read-only financial visibility.
   - TECH-0153: share fact reads, narrow room-detail queries and bound subscription entitlement query counts.
   - TECH-0154: preserve the owner-approved unlimited historical export range while making large exports memory-bounded and recovering stale XLSX jobs; tenant-safe claims, SQL-filtered cleanup and idempotency fixes are implemented.
   - TECH-0155: enforce monthly AI quotas atomically without keeping database connections open during inference.
   - TECH-0156–0157: confirm no-show/rounding and trial/comped-expiration semantics before changing historical financial or subscription behavior.
   - TECH-0158: use the fresh selective permission resolver for one-capability request guards without adding authorization cache.
   - TECH-0159: avoid hydrating guest stay history and tags in list/search responses while retaining companions.
   - TECH-0160: debounce global reservation search and avoid showing stale results.
   - TECH-0161: scope rate-change invalidation to the affected category and its quote data.
   - TECH-0162: defer hidden mobile laundry queries and cross-tab refreshes until a tab is visible.
   - TECH-0063: repeat local capacity runs from [the audit report](audits/auditoria-eficiencia-capacidad-y-reglas-operativas-2026-10-15.md); add services only when CPU, memory, p95 or database evidence crosses the listed thresholds.

## Practical rule
- Do not expand into new product areas until the pilot core is stable.
- Prefer small, testable milestones that improve real hotel operation.

