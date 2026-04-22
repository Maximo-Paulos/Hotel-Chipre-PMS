# Security Baseline

## Principles
- Fail closed in production.
- Validate all external input.
- Scope every sensitive action by hotel and authenticated user.
- Redact PII before sending text to Gemma or logs.
- Keep secrets in environment variables, never in source.

## Current security controls in the repo
- Production runtime validation already rejects weak placeholder secrets and invalid public URLs.
- Auth uses bearer tokens plus hotel/user headers on protected API calls.
- Webhook and integration flows use scoped credentials and secret checks.
- Gemma keeps messages, insights, and actions scoped per hotel and user.
- Demo-only endpoints are separated from normal runtime behavior.

## Required environment hardening
- `APP_ENV` must clearly distinguish development, testing, and production.
- `JWT_SECRET` must be strong and non-default in production.
- `MASTER_ADMIN_PIN` must not use the bundled default in production.
- `INTEGRATIONS_ENCRYPTION_KEY` must be a valid Fernet key in production.
- `APP_BASE_URL` must be public HTTPS in production.
- OAuth and webhook redirect URLs must use public HTTPS in production.
- Merchant, OTA, Redis, and Gemma credentials must come from env/config.
- System mail is managed from `/adminpmsmaster` via Gmail OAuth; the connection must be persisted securely and may not fall back to SMTP or exposed auth codes.

## Operational rule
- If a security requirement is ambiguous, choose the safer behavior and escalate rather than guessing.
