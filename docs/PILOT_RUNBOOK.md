# Pilot Runbook

## Objective

Execute a controlled pilot of Hotel-Chipre-PMS with a repeatable preflight, operational verification path, and clear stop conditions.

## Preflight

Run from `C:\PROJECTO\Hotel-Chipre-PMS`:

```powershell
python -m alembic upgrade head
python -m pytest tests/smoke/ -v
python -m pytest -q
cd frontend
npm run build
cd ..
```

If `npm run lint` is required for release review, run it separately and treat existing unrelated lint errors as a known baseline until they are cleaned.

## Pilot Start Checklist

1. Confirm migrations are applied on the pilot database.
2. Confirm an owner can register and verify email.
3. Confirm onboarding can complete with identity, categories, rooms, policy, payments, OTA channels, subscription choice, and staff.
4. Confirm subscription state is operational: `active`, `trialing`, `demo`, or `comped`.
5. Confirm at least one room category and one room exist before opening the hotel to reservations.

## Operational Smoke Path

### 1. Channel connectivity

Verify provider connection upsert:

```powershell
python -m pytest tests/smoke/test_connect_channels_smoke.py -v
```

Expected result:
- provider returns `connected`
- reconnect updates the same connection record

### 2. Manual review resolution

Verify front-office recovery for flagged reservations:

```powershell
python -m pytest tests/smoke/test_manual_review_resolution.py -v
```

Expected result:
- reservation starts in `requires_manual_review=true`
- clearing review removes the flag
- allocation state moves out of `manual_review`

### 3. Reservation operations

Verify check-in and check-out:

```powershell
python -m pytest tests/smoke/test_reservation_operations.py -v
```

Expected result:
- guest validation passes
- check-in changes reservation to `checked_in`
- check-out changes reservation to `checked_out`

### 4. Payment failures

Verify safe rejection paths:

```powershell
python -m pytest tests/smoke/test_payment_failures.py -v
```

Expected result:
- overpayment is rejected
- disabled payment methods are rejected

## Production-Minded Pilot Rules

- Do not enable unfinished AI or Gemma flows during pilot.
- Do not bypass auth headers or hotel scoping for manual checks.
- Treat payment, reservation, and onboarding errors as operational incidents, not UI-only defects.
- Preserve hotel isolation when validating data from more than one tenant.

## Stop Conditions

Pause the pilot immediately if any of the following occurs:

- migrations fail or drift from the app models
- owner onboarding cannot finish with all required gates satisfied
- reservations can be created or mutated while subscription is non-operational
- check-in succeeds without required guest identity or terms data
- payments are accepted beyond balance due
- manual review flags cannot be cleared by an authorized operator

## Rollback / Containment

1. Stop new pilot onboarding.
2. Capture failing command output and affected hotel id.
3. Re-run the narrow smoke target for the failing area.
4. If the issue persists, keep the pilot in read-only operational mode for the affected workflow.
5. Patch in a feature branch, validate locally, and redeploy only the corrected build.
