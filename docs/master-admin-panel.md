# Owner Master Panel

## Scope

The owner master panel is isolated under `/adminpmsmaster` and is backed by a separate backend module at `app/master_admin/`.

It provides:

- master-only authentication with a separate session store
- separate CSRF protection for master writes
- dashboard visibility for hotel and subscription state
- centralized billing policy management
- email provider abstraction and test endpoint
- Stripe webhook base with signature verification
- audit event collection for master actions

## Backend entrypoints

- `POST /api/master-admin/auth/login`
- `POST /api/master-admin/auth/logout`
- `GET /api/master-admin/auth/me`
- `GET /api/master-admin/dashboard/summary`
- `GET /api/master-admin/dashboard/hotels`
- `GET|PUT /api/master-admin/billing/policy`
- `GET /api/master-admin/email/providers`
- `POST /api/master-admin/email/test`
- `GET /api/master-admin/stripe/config`
- `POST /api/master-admin/stripe/webhook`
- `GET /api/master-admin/audit/events`

## Frontend routes

- `/adminpmsmaster`
- `/adminpmsmaster/login`
- `/adminpmsmaster/dashboard`
- `/adminpmsmaster/billing`
- `/adminpmsmaster/email`
- `/adminpmsmaster/stripe`
- `/adminpmsmaster/audit`

## Key environment variables

- `MANAGER_PIN`
- `MASTER_STRIPE_WEBHOOK_SECRET`
- `STRIPE_WEBHOOK_SECRET`
- `EMAIL_PROVIDER`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASS`
- `SMTP_FROM`
- `TRANSACTIONAL_EMAIL_ENDPOINT`
- `TRANSACTIONAL_EMAIL_API_KEY`

## Validation

Backend regression coverage lives in `tests/test_master_admin_panel.py`.
The master panel-specific backend tests pass.

