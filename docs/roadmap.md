# Roadmap

This repository is currently in the pilot-to-public transition described in `docs/master-plan-pilot-to-public.md`.

## Current state
- The backend already covers reservations, rooms, payments, onboarding, OTA intake, allocation, auth, subscriptions, and Gemma.
- The frontend already has the public auth flows, onboarding, and protected operational screens.
- The current focus is pilot readiness, not a broad rewrite.

## Current direction
1. Close the operational core for pilot use.
   - OTA inbound lifecycle: new, modified, cancelled, duplicate.
   - Allocation behavior: fragmentation, manual review, policy/runtime loop.
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

## Practical rule
- Do not expand into new product areas until the pilot core is stable.
- Prefer small, testable milestones that improve real hotel operation.

