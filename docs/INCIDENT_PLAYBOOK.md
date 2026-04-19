# Incident Playbook

## Purpose

Provide a concrete response path for pilot incidents affecting onboarding, subscriptions, reservations, channel operations, and payments.

## Severity Levels

- `SEV-1`: data integrity or payment integrity risk, or hotel operations blocked across multiple workflows
- `SEV-2`: one critical workflow blocked for one or more hotels
- `SEV-3`: degraded behavior with workaround available

## First Response

1. Record timestamp, hotel id, user role, and endpoint involved.
2. Capture the failing request payload without secrets.
3. Reproduce locally against the current branch if possible.
4. Run the narrowest relevant test target before changing code.

## Incident Types

### Reservation manual review incident

Symptoms:
- reservation stays in `requires_manual_review=true`
- allocation remains `manual_review`

Commands:

```powershell
python -m pytest tests/smoke/test_manual_review_resolution.py -v
```

Containment:
- keep reservation out of automated allocation follow-up
- clear the flag only through the authorized reservation operations endpoint

### Payment rejection or over-collection incident

Symptoms:
- payment accepted beyond balance due
- disabled method accepted
- summary amounts drift from expected reservation balance

Commands:

```powershell
python -m pytest tests/smoke/test_payment_failures.py -v
```

Containment:
- stop operator retries on the same reservation until summary is reviewed
- inspect reservation financial summary via `/api/payments/summary/{reservation_id}`

### Reservation lifecycle incident

Symptoms:
- guest validation passes with incomplete identity
- check-in or check-out transitions fail unexpectedly

Commands:

```powershell
python -m pytest tests/smoke/test_reservation_operations.py -v
```

Containment:
- avoid manual DB edits to reservation status
- recover through the API path after root cause is identified

### Channel connectivity incident

Symptoms:
- channel reconnect creates duplicate provider rows
- provider settings do not persist on reconnect

Commands:

```powershell
python -m pytest tests/smoke/test_connect_channels_smoke.py -v
```

Containment:
- pause additional reconnect attempts until one successful idempotent connect is confirmed

### Onboarding / subscription gating incident

Symptoms:
- onboarding finish remains disabled after completing visible steps
- operators can finish onboarding without identity or operational subscription

Commands:

```powershell
python -m pytest tests/test_onboarding_gates.py tests/test_onboarding_wizard.py -q
python -m pytest tests/test_subscription_tiers.py -q
```

Containment:
- keep hotel in onboarding state
- verify `GET /api/onboarding/status` gates payload before any manual intervention

## Escalation Data

When escalating to another engineer, include:

- exact failing command
- endpoint and payload shape
- hotel id and user role
- current migration head
- whether failure reproduces on SQLite smoke DB and primary dev DB

## Deferred Area

Gemma smoke validation remains intentionally deferred until the final IA configuration phase. Do not open incidents against the current pilot for missing Gemma smoke coverage alone.
