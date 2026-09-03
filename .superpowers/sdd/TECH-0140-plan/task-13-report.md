# TECH-0140 — T13 release gate report

## Implemented

- Added `scripts/scale/staged_realtime_load.py` as a bounded, authenticated,
  GET-only runner for recovery and SSE against an isolated preview.
- The runner rejects the shared production hosts, requires
  `LOADTEST_BEARER_TOKEN`, reports recovery status/latency, SSE readiness,
  heartbeats and errors, and never creates reservations, payments or other
  business writes.
- Added `docs/runbooks/tech0140-release-gate.md` with reproducible local gates,
  provider-bound evidence requirements and stop thresholds.
- Added tests for the load runner target guard and enabled the static GCP
  readiness validator in pull-request backend validation.
- SSE now performs periodic authorization revalidation using a short-lived DB
  session. A revoked user receives a control event and the stream closes.

## Verification

Focused gate:

```text
66 passed, 16 warnings
```

The warnings are existing dependency deprecations and SQLAlchemy relationship
overlap warnings; they do not fail the gate. Provider-bound staging load,
browser E2E and signed release evidence remain intentionally unexecuted.

Final local verification also completed:

```text
1921 passed, 26 skipped, 12 xfailed, 1 xpassed, 35 warnings
frontend: lint, typecheck, build, PWA 3/3, build metadata 3/3, i18n 2/2
Alembic: tech0140_job_runtime (head) from an empty SQLite database
GCP readiness: ready-for-provider-validation
dependency audit: npm runtime 0 vulnerabilities; two development-tooling
vulnerabilities remain because the available Vite fix is a major upgrade
requiring a separate migration; `pip-audit` is not installed locally
```

## Release decision

`BLOCKED` until a human-authorized isolated staging run produces current
SHA-bound `summary.json`, `validated-preview-manifest.json` and signed
`attestation.json`, and the provider-bound restore, security and load checks
are reviewed. No production traffic, billing, OAuth configuration, cloud
resource or real business data was changed by T13.
