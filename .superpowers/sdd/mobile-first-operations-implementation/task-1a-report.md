# Task 1A — RBAC implementation report

## Summary

Implemented the additive RBAC expansion on `feature/mobile-first-operations`: explicit operational permission keys, safe legacy aliases, tenant-scoped per-user overrides, role and user administration APIs, effective-access preview, audit records, and cross-worker invalidation events. Resolution is deny-by-default and follows `invariant > user override > hotel role override > role default > deny`.

Only `owner` can administer permissions. Owner-only invariants cannot be delegated or removed, per-user grants cannot exceed the target role ceiling, and attempts to elevate the acting owner or reference another hotel's membership are rejected without disclosing membership existence.

## Main files

- `app/services/permission_service.py`: canonical catalog, legacy mapping, default role matrix, invariant and precedence resolution, mutation/restore services, audit snapshots, invalidation hook.
- `app/models/permission.py`: tenant-scoped `UserPermissionOverride` with composite membership foreign key and audit metadata.
- `app/api/permissions.py`, `app/schemas/permission.py`: catalog, role override, user override, effective/preview, and restore contracts with source/lock metadata.
- `app/dependencies/auth.py` and sensitive API modules: user-aware permission resolution and owner-only permission administration.
- `alembic/versions/20260813_rbac_user_overrides.py`: linear expand/contract migration, legacy decision translation, PostgreSQL RLS owned by the new migration, and reversible SQLite/PostgreSQL downgrade path.
- `tests/test_permission_overrides_v2.py`, `tests/test_rbac_user_overrides_migration.py`: role matrix, invariants, precedence, immediate invalidation behavior, audit, API authorization, tenant isolation, nondisclosure, and migration round-trip coverage.

## TDD evidence

RED:

```text
python -m pytest -q tests/test_permission_overrides_v2.py
ERROR collecting ... ImportError: cannot import name 'UserPermissionOverride'
```

GREEN focused:

```text
python -m pytest -q tests/test_permission_overrides_v2.py tests/test_permission_overrides.py tests/test_permission_api.py tests/test_rbac_user_overrides_migration.py
23 passed
```

Affected backend slice:

```text
python -m pytest -q tests/test_permission_overrides_v2.py tests/test_permission_overrides.py tests/test_permission_api.py tests/test_rbac_user_overrides_migration.py tests/test_rbac_scope_inventory.py tests/test_reservation_permission_access.py tests/test_checkin_permissions.py tests/test_checkout_permissions.py tests/test_stock_permissions.py tests/test_reports_permissions.py tests/test_analytics_permissions.py tests/test_cash_register_permissions.py
55 passed
```

Full backend suite:

```text
/Users/maximopaulos/AI-Workspace/worktrees/hotel-chipre-pms-scale-hardening/.venv/bin/python -m pytest -q
1468 passed, 22 skipped, 12 xfailed, 1 xpassed, 29 warnings in 141.13s
```

The shared scale-hardening virtualenv was used because this worktree's default environment lacked `google.auth`; no application dependency or code was changed to bypass that environment issue.

## Migration validation

A clean temporary SQLite database completed `upgrade head -> downgrade 20260812_external_effects -> upgrade head`; `alembic current` and `alembic heads` both ended at the single head `20260813_rbac_overrides`. The focused migration regression test also passed after removing the compatibility-risk edit to the historical RLS migration; the new migration owns the new table and its PostgreSQL RLS policy.

## Security review

- Authorization is deny-by-default; direct permission-management access is owner-only.
- All user override reads and writes bind through `(hotel_id, user_id)` membership identity.
- Cross-hotel and unknown user identifiers return the same not-found response.
- Audit payloads contain permission decisions and actor/target identifiers, not credentials, sessions, secrets, payment data, or guest PII.
- No effective-permission result cache is retained in-process. Successful mutation commits publish a tenant-scoped `permissions.changed` event; stale cross-worker grants therefore cannot survive a mutation.
- Legacy permission names remain readable and are resolved through explicit aliases while canonical keys are the persisted forward contract.

## Documentation and Graphify

Generated API, OpenAPI, migration-head, and surface inventories were refreshed. `graphify update . --no-description --no-label` rebuilt the portable AST graph without API cost. `graphify check-update .` still reports semantic descriptions/labels pending (`.graphify_describe_pending`); completing the 228 generated description batches requires the separate semantic-enrichment workflow and is the only outstanding repository-knowledge gate.

## Risks / limitations

- PostgreSQL RLS DDL is covered structurally and by existing inventory expectations; the executable up/down/up proof in this worktree used SQLite.
- Downgrading intentionally contracts canonical decisions back to the nearest legacy permission and removes canonical-only/user-override data, as required by the prior schema contract.
- Existing SQLAlchemy relationship overlap and framework deprecation warnings remain unchanged.

## Recommended next step

Run Graphify semantic enrichment, then validate the migration against an isolated PostgreSQL preview before release promotion.

## Fix round 1 — canonical route enforcement and RLS evidence

### Review findings closed

- Replaced static role guards and the legacy `stock:operate` route guard with canonical action permissions before handler reads or mutations. Covered reservation read/create/update/cancel/move/manual-rate/check-in/check-out, stock read/movement/adjust/admin, room read/status, laundry read/movement, and rate read/update routes, including the alternate rate-calendar read path.
- Preserved the narrow manager-only room mutation and OTA no-guarantee reconciliation lanes only as secondary product boundaries after canonical permission resolution. Housekeeping keeps the dedicated constrained cleaning-status path and never gains generic room configuration mutation.
- Protected integration connect, manual callback, revoke, and refresh with immutable owner-only `hotel_settings:security_manage`. The public provider callback revalidates the signed-state actor's active `(hotel_id, user_id)` membership and owner-only effective permission before any code exchange or credential storage.
- Changed runtime role-default seeding to insert missing rows only, so migration/backfilled decisions are never overwritten during permission resolution.
- Kept PostgreSQL RLS DDL in the additive `20260813_rbac_overrides` migration and added an Alembic PostgreSQL offline-recorder contract that executes the install/remove helpers through `MigrationContext` and `Operations`, then verifies ordered `ENABLE`, `FORCE`, policy `USING`/`WITH CHECK`, `DROP`, `NO FORCE`, and `DISABLE` statements.

### TDD evidence

Initial review regressions were captured before implementation:

```text
/Users/maximopaulos/AI-Workspace/worktrees/hotel-chipre-pms-scale-hardening/.venv/bin/python -m pytest -q tests/test_rbac_sensitive_route_permissions.py tests/test_integration_security_permissions.py tests/test_permission_overrides_v2.py::test_runtime_seeding_never_overwrites_existing_backfilled_default tests/test_rbac_user_overrides_migration.py::test_postgresql_rls_contract_executes_enable_policy_and_downgrade_removal
5 failed, 21 warnings in 1.23s
```

The follow-up room/laundry/rates bypasses were also demonstrated before their guards changed:

```text
/Users/maximopaulos/AI-Workspace/worktrees/hotel-chipre-pms-scale-hardening/.venv/bin/python -m pytest -q --disable-warnings tests/test_rbac_sensitive_route_permissions.py -k 'room_read or laundry_read or rate_read'
3 failed, 3 deselected, 21 warnings in 1.05s
```

Final focused security and migration contract run:

```text
/Users/maximopaulos/AI-Workspace/worktrees/hotel-chipre-pms-scale-hardening/.venv/bin/python -m pytest -q --disable-warnings tests/test_rbac_sensitive_route_permissions.py tests/test_integration_security_permissions.py tests/test_permission_overrides_v2.py::test_runtime_seeding_never_overwrites_existing_backfilled_default tests/test_rbac_user_overrides_migration.py::test_postgresql_rls_contract_executes_enable_policy_and_downgrade_removal tests/test_tenant_rls_contract.py::test_user_override_rls_round_trip_records_valid_postgresql_ddl
10 passed, 23 warnings in 1.81s
```

The HTTP regressions explicitly revoke and grant each route-family permission and assert that a denied response leaks no protected data and performs no partial mutation.

### Affected validation

```text
/Users/maximopaulos/AI-Workspace/worktrees/hotel-chipre-pms-scale-hardening/.venv/bin/python -m pytest -q --disable-warnings tests/test_rooms_api_roles.py tests/test_rooms_schema.py tests/test_api_scaffolding.py tests/test_room_blocks_api.py tests/test_room_block_service.py tests/test_room_movement_groups_api.py tests/test_laundry_service.py tests/test_laundry_vendor_api.py tests/test_laundry_vendor_service.py tests/test_v72_daily_rates.py tests/test_rate_calendar_api.py tests/test_rate_calendar_service.py tests/test_v72_fx_rates.py tests/test_audit_coverage.py tests/test_cross_hotel_id_collision_api.py tests/test_permission_service.py tests/test_permission_overrides_v2.py tests/test_rbac_sensitive_route_permissions.py tests/test_integration_security_permissions.py tests/test_rbac_user_overrides_migration.py tests/test_tenant_rls_contract.py
165 passed, 25 warnings in 13.09s
```

```text
/Users/maximopaulos/AI-Workspace/worktrees/hotel-chipre-pms-scale-hardening/.venv/bin/python -m pytest -q --disable-warnings tests/test_role_contracts.py tests/test_route_security_guardrail.py tests/test_reservation_manual_rate_permission.py tests/test_v72_mobility.py tests/test_checkin_override_api.py tests/test_stock_api.py tests/test_stock_service.py tests/smoke/test_connect_channels_smoke.py tests/test_gmail_outbound_flow.py
40 passed, 21 warnings in 3.80s
```

An earlier affected slice covering reservations, check-in, stock, integrations, authorization, and tenant collisions also completed with `134 passed, 1 xfailed, 24 warnings in 14.28s`.

The first full-suite run correctly exposed two compatibility regressions: the manager-only no-guarantee release lane and the historical baseline RLS inventory expectation. Both received focused fixes and regressions; the intermediate retry completed with `1474 passed, 22 skipped, 12 xfailed, 1 xpassed`.

Final full backend suite after all route-family fixes:

```text
/Users/maximopaulos/AI-Workspace/worktrees/hotel-chipre-pms-scale-hardening/.venv/bin/python -m pytest -q --disable-warnings
1478 passed, 22 skipped, 12 xfailed, 1 xpassed, 29 warnings in 138.53s (0:02:18)
```

`python -m compileall -q` on every changed Python module and `git diff --check` both completed successfully.

### Migration validation and PostgreSQL limitation

A new temporary SQLite database completed:

```text
python -m alembic upgrade head
python -m alembic downgrade 20260812_external_effects
python -m alembic upgrade head
python -m alembic current
python -m alembic heads
20260813_rbac_overrides (head)
20260813_rbac_overrides (head)
```

No production, preview, or developer PostgreSQL database was contacted. The deterministic PostgreSQL evidence compiles and records the real migration helpers with Alembic's PostgreSQL dialect, so it validates emitted DDL and order without external state. It does not prove server execution, privileges, or live policy behavior; an isolated preview PostgreSQL up/down/up remains a release-time validation requirement.

### Security review

- Permission dependencies execute before tenant-scoped queries or mutations. Conditional permissions such as force checkout, manual rate, room move, and stock adjustment are resolved before their handler performs work.
- All route data access continues to bind `context.hotel_id`; new HTTP tests cover denied-response nondisclosure and existing cross-hotel collision tests remain green.
- Credential mutations are owner-only, and the bearer-less OAuth callback rechecks current membership and effective permission before token exchange/storage.
- No credentials, OAuth codes, webhook values, sessions, payment data, guest PII, or external effects were written to tests, logs, the report, or memory checkpoints.
- A second independent fix-round review found no remaining Task 1A blockers.

### Documentation and generated artifacts

This implementation report is the only documentation artifact updated in the fix round. Per fix-round instruction, Graphify and generated inventories were not regenerated; the pre-existing semantic-enrichment pending state therefore remains a separate repository-knowledge/release gate.
