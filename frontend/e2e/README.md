# Playwright E2E

These specs use the real Vite frontend on `http://127.0.0.1:5173` and the real FastAPI backend on `http://127.0.0.1:8040`. Every database-backed E2E run requires a fresh, isolated PostgreSQL 16 database in Colima; SQLite is not supported.

## Managed run

Before starting Playwright, prepare a fresh Colima PostgreSQL 16 database and
the dedicated app/seed roles described below, then export all five explicit
E2E PostgreSQL variables. The config exits before starting either server if
any variable is missing or does not match the isolated target.

From `frontend/`:

```bash
npm install
npx playwright install chromium
npm run e2e -- e2e/v72-pages.spec.ts
```

The responsive smoke can also run against Playwright WebKit's iPhone
descriptors (this is WebKit emulation, not an Xcode Safari Simulator):

```bash
npx playwright install webkit
E2E_PYTHON=/absolute/path/to/python3.12 npx playwright test \
  e2e/responsive-smoke.spec.ts \
  --project=webkit-iphone-se \
  --project=webkit-iphone-15 \
  --project=webkit-iphone-15-pro-max

# Critical business journey in an iPhone-sized WebKit context
E2E_WEBKIT_BUSINESS=true E2E_PYTHON=/absolute/path/to/python3.12 npx playwright test \
  e2e/business-journey.spec.ts \
  --project=webkit-iphone-15-business
```

The WebKit business project is opt-in because the Chromium and WebKit
journeys both mutate the same isolated PostgreSQL database. Run it as a separate
command after the default suite, never concurrently with another mutating
project.

`playwright.config.ts` requires Python 3.10+ and selects `.venv312`, then
`.venv`, then a supported interpreter on `PATH`. If the repository has a
legacy Python 3.9 environment, pass the interpreter explicitly:

```bash
E2E_PYTHON=/absolute/path/to/python3.12 npm run e2e
```

It migrates and seeds the explicitly selected PostgreSQL database, starts
`uvicorn app.main:app --port 8040`, then starts Vite with
`VITE_PUBLIC_APP_HOSTNAME=127.0.0.1`. The runner refuses missing, remote,
reused, or non-PostgreSQL database targets before migration or seeding.
For reliable isolation, existing servers are not reused by default. Set
`E2E_REUSE_SERVER=true` only when intentionally connecting to already-running
servers; in that mode the runner does not own their database state.

### PostgreSQL 16 browser runs

Use a new, empty local PostgreSQL 16 database and two dedicated login roles
for each run. The database and both role names must begin with
`hotel_chipre_e2e_`; the app role must end in `_app_runner`, and the seed role
must end in `_seed_runner`. The database endpoint must be loopback on port
5432, or a local port in 55000–55999 if 5432 is occupied. Keep the database
synthetic-only. The seed refuses PostgreSQL unless
both URLs are passed twice as explicit opt-ins, and it checks that the
`public` schema has no user objects before migrations. It never drops,
truncates, or resets a PostgreSQL database. Reusing a migrated database is
rejected; create a fresh one for the next run and remove only the database and
roles created for that run after validation.

The browser backend always uses the regular `_app_runner` role, so RLS remains
active during user flows. The separate `_seed_runner` role is used only to
load fixtures before the app starts; it must have `BYPASSRLS` and receives
table/sequence grants only on the freshly migrated synthetic test database.
Do not use the seed role in the app URL.

Set `E2E_DATABASE_URL` to that local DSN, then set
`E2E_POSTGRES_ISOLATED=true` and
`E2E_POSTGRES_DATABASE_URL_EXPLICIT` to the exact same app-role DSN. Set
`E2E_POSTGRES_SEED_DATABASE_URL` and
`E2E_POSTGRES_SEED_DATABASE_URL_EXPLICIT` to the exact same seed-role DSN. Both
DSNs must point to the same local database. The normal test server still
forces external effects, provider connections, and inbound provider events
off.

For the focused `tax-policy-setup.spec.ts`, set `E2E_TAX_POLICY_SETUP=true`.
This seeds the same synthetic hotel and users but deliberately omits its zero-tax
policy so the browser test can create one in Settings. Do not combine this flag
with unrelated reservation flows, which correctly refuse to quote without an
active hotel policy.

## Manual boot

Set the five explicit PostgreSQL variables described above, then run
`python scripts/serve_e2e_backend.py` from the repository root. The wrapper
performs the same PostgreSQL target checks as the managed Playwright run.

### F-003 concurrent-user load fixture

`f003-concurrent-user-load.spec.ts` is an opt-in 30-minute PostgreSQL load run. Set `E2E_F003_LOAD=true` only with a fresh, loopback PostgreSQL 16 database named `hotel_chipre_e2e_f003_load_*`, plus its matching `_app_runner` and `_seed_runner` roles and explicit isolated database URL settings. The dedicated seed then creates the synthetic Hotel Mirador del Lago with 30 rooms and 45 reservations. It refuses SQLite, other database names, non-isolated targets, or a database that does not contain the untouched base E2E fixture. The shared E2E seed remains unchanged.

El seed/wrapper rechaza SQLite, destinos remotos, bases reutilizadas y
cualquier `APP_ENV` distinto de `test` antes de importar Alembic/FastAPI.

In another shell from `frontend/`:

```bash
VITE_PUBLIC_APP_HOSTNAME=127.0.0.1 VITE_API_URL=http://127.0.0.1:8040/api npm run dev -- --host 127.0.0.1
npx playwright test e2e/v72-pages.spec.ts
```

Login seed:

- Email: `owner@e2e.com`
- Password: `E2ePass1234!`

Screenshots are written to `frontend/e2e/screenshots/`.
