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
