# Playwright E2E

These specs use the real Vite frontend on `http://127.0.0.1:5173` and the real FastAPI backend on `http://127.0.0.1:8040`.

## Managed run

From `frontend/`:

```bash
npm install
npx playwright install chromium
npm run e2e -- e2e/v72-pages.spec.ts
```

`playwright.config.ts` seeds `../_e2e.db`, starts `uvicorn app.main:app --port 8040`, then starts Vite with `VITE_PUBLIC_APP_HOSTNAME=127.0.0.1`.

## Manual boot

From the repository root:

```bash
DATABASE_URL=sqlite:///./_e2e.db JWT_SECRET=e2e-local-jwt-secret-change-me-32chars python scripts/seed_e2e_backend.py
DATABASE_URL=sqlite:///./_e2e.db JWT_SECRET=e2e-local-jwt-secret-change-me-32chars uvicorn app.main:app --host 127.0.0.1 --port 8040
```

Or use the single-command wrapper:

```bash
python scripts/serve_e2e_backend.py
```

In another shell from `frontend/`:

```bash
VITE_PUBLIC_APP_HOSTNAME=127.0.0.1 VITE_API_URL=http://127.0.0.1:8040/api npm run dev -- --host 127.0.0.1
npx playwright test e2e/v72-pages.spec.ts
```

Login seed:

- Email: `owner@e2e.com`
- Password: `E2ePass1234!`

Screenshots are written to `frontend/e2e/screenshots/`.
