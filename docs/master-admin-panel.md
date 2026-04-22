# Owner Master Panel

## Scope

The owner master panel is isolated under `/adminpmsmaster` and is backed by `app/master_admin/`.

It provides:

- master-only authentication with a separate session store
- separate CSRF protection for master writes
- dashboard visibility for hotel and subscription state
- centralized billing policy management with `exempt_hotel_ids` and `exempt_user_ids`
- Gmail OAuth connection for the system mail provider
- Stripe owner configuration with secure persistence
- audit event collection for master actions

## Backend entrypoints

- `POST /api/master-admin/auth/login`
- `POST /api/master-admin/auth/logout`
- `GET /api/master-admin/auth/me`
- `GET /api/master-admin/dashboard/summary`
- `GET /api/master-admin/dashboard/hotels`
- `GET|PUT /api/master-admin/billing/policy`
- `GET /api/master-admin/email/status`
- `GET /api/master-admin/email/providers`
- `POST /api/master-admin/email/connect`
- `GET /api/master-admin/email/oauth/gmail/callback`
- `POST /api/master-admin/email/disconnect`
- `POST /api/master-admin/email/test`
- `GET /api/master-admin/stripe/config`
- `POST /api/master-admin/stripe/connect`
- `POST /api/master-admin/stripe/disconnect`
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

- `MASTER_ADMIN_EMAIL`
- `MASTER_ADMIN_PASSWORD`
- `MASTER_ADMIN_PIN`
- `GOOGLE_OAUTH_REDIRECT_URI`  (alias compatible with `MASTER_EMAIL_GMAIL_REDIRECT_URI`)
- `GOOGLE_OAUTH_CLIENT_ID`  (alias compatible with `GMAIL_CLIENT_ID`)
- `GOOGLE_OAUTH_CLIENT_SECRET`  (alias compatible with `GMAIL_CLIENT_SECRET`)
- `MASTER_STRIPE_WEBHOOK_SECRET`
- `STRIPE_WEBHOOK_SECRET`
- `INTEGRATIONS_ENCRYPTION_KEY`
- `APP_BASE_URL`
- `FRONTEND_URL`

## Validation

Backend regression coverage lives in `tests/test_master_admin_panel.py`.
The master panel-specific backend tests pass.
