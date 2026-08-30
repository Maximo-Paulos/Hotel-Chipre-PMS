# Deduplication sweep: onboarding, configuration, pricing, and settings

## Goal

Remove divergent write paths and invisible configuration layers while preserving
tenant scoping, permission-driven navigation, and the existing 13-test baseline.

## Implementation sequence

1. Add regression tests for the room-status side effects, onboarding category
   parity, onboarding staff invitations, and configuration authority.
2. Extract shared room-state and staff-invitation services. Make the generic
   room patch, status patch, user invite route, and onboarding staff step use
   those services.
3. Extract shared hotel-configuration/category/room write helpers. Repoint
   onboarding steps to the same domain writes used by Settings and stop reading
   onboarding JSON or `extra_policies` as runtime configuration.
4. Add authoritative hotel configuration columns for identity, OTA, payment,
   and report-recipient data. Remove or implement the listed dead fields with a
   reversible Alembic migration.
5. Retire `category_pricing`: verify existing rows, add per-method fields to
   `price_periods`, migrate legacy rows into low-priority periods, and remove
   active runtime/API resolution of the legacy table.
6. Add seasonal-price CRUD UI to the rate calendar and show effective price plus
   winning layer in Settings > Hotel.
7. Consolidate WhatsApp under Conexiones, centralize the duplicated room/API-key
   query keys, and remove the duplicate WhatsApp cache surface.
8. Run focused tests, Alembic upgrade/downgrade/upgrade, Graphify refresh, the
   frontend gate, the role journey, and the full pytest comparison from repo
   root.

## Decisions to verify in code

- Onboarding creates pending staff invitations without sending email; email
  remains an explicit Settings action until a safe post-finish delivery path is
  available.
- `allow_overbooking` is retained because it represents a real operational
  policy and gets a reader/UI; role-specific revenue flags are removed because
  permission policy is the canonical control.
- Other listed fields with no reader or product surface are removed rather than
  leaving writes that cannot affect behavior.
- Legacy category-pricing data is preserved in a renamed archive table and
  folded into `price_periods`; no local rows are expected, but the migration is
  data-safe for other hotels.

## Verification gates

- `.venv/bin/python -m pytest -q` from the repository root; only the exact known
  13 failure names may remain, with added tests increasing the pass count.
- `.venv/bin/alembic heads`, then `upgrade head`, `downgrade -1`, and `upgrade
  head`, with one head throughout.
- `frontend`: `npm run lint`, `npm run typecheck`, and `npm run build` using the
  requested Node 20 PATH.
- `frontend/e2e/role-journey.spec.ts` remains green when its browser runner is
  available.
