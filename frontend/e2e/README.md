# Playwright E2E

These specs use the real Vite frontend on `http://127.0.0.1:5173` and the real FastAPI backend on `http://127.0.0.1:8040`.

## Managed run

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
journeys both mutate the same isolated SQLite database. Run it as a separate
command after the default suite, never concurrently with another mutating
project.

`playwright.config.ts` requires Python 3.10+ and selects `.venv312`, then
`.venv`, then a supported interpreter on `PATH`. If the repository has a
legacy Python 3.9 environment, pass the interpreter explicitly:

```bash
E2E_PYTHON=/absolute/path/to/python3.12 npm run e2e
```

It resets and seeds `../_e2e.db`, starts `uvicorn app.main:app --port 8040`,
then starts Vite with `VITE_PUBLIC_APP_HOSTNAME=127.0.0.1`. The business
journey mutates this isolated database, and the managed runner resets it on
each invocation so an old open cash session cannot contaminate a fresh run.
For reliable isolation, existing servers are not reused by default. Set
`E2E_REUSE_SERVER=true` only when intentionally connecting to already-running
servers; in that mode the runner does not reset or own their database state.

### PostgreSQL 16 browser runs

Use a new, empty local PostgreSQL 16 database and two dedicated login roles
for each run. The database and both role names must begin with
`hotel_chipre_e2e_`; the app role must end in `_app_runner`, and the seed role
must end in `_seed_runner`. The database endpoint must be loopback on port
5432. Keep the database synthetic-only. The seed refuses PostgreSQL unless
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

## Manual boot

From the repository root:

```bash
APP_ENV=test DATABASE_URL=sqlite:///./_e2e.db JWT_SECRET=e2e-local-jwt-secret-change-me-32chars python scripts/seed_e2e_backend.py
APP_ENV=test DATABASE_URL=sqlite:///./_e2e.db JWT_SECRET=e2e-local-jwt-secret-change-me-32chars uvicorn app.main:app --host 127.0.0.1 --port 8040
```

Or use the single-command wrapper:

```bash
APP_ENV=test DATABASE_URL=sqlite:///./_e2e.db python scripts/serve_e2e_backend.py
```

### F-003 concurrent-user load fixture

`f003-concurrent-user-load.spec.ts` is an opt-in 30-minute PostgreSQL load run. Set `E2E_F003_LOAD=true` only with a fresh, loopback PostgreSQL 16 database named `hotel_chipre_e2e_f003_load_*`, plus its matching `_app_runner` and `_seed_runner` roles and explicit isolated database URL settings. The dedicated seed then creates the synthetic Hotel Mirador del Lago with 30 rooms and 45 reservations. It refuses SQLite, other database names, non-isolated targets, or a database that does not contain the untouched base E2E fixture. The shared E2E seed remains unchanged.

El seed/wrapper admite SQLite sólo en el path exacto `_e2e.db` del repositorio,
o PostgreSQL 16 local con la opt-in y el nombre de base/rol desechables
descritos arriba. Rechaza destinos remotos, otros esquemas y cualquier
`APP_ENV` distinto de `test` antes de importar Alembic/FastAPI.

In another shell from `frontend/`:

```bash
VITE_PUBLIC_APP_HOSTNAME=127.0.0.1 VITE_API_URL=http://127.0.0.1:8040/api npm run dev -- --host 127.0.0.1
npx playwright test e2e/v72-pages.spec.ts
```

Login seed:

- Email: `owner@e2e.com`
- Password: `E2ePass1234!`

Screenshots are written to `frontend/e2e/screenshots/`.
