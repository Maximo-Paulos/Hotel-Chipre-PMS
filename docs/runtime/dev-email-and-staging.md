# Dev email and staging runtime

## Development email minimum

For local validation of `register-owner -> verify-email -> onboarding/status`, the backend should run with:

- `APP_ENV=development`
- `TESTING=true`
- `DEV_EMAIL_OUTBOX_PATH=<workspace>/tmp/dev-email-outbox.jsonl` or leave empty to use the system temp fallback

In development and non-production modes, transactional email is captured as a dev no-op and written to the outbox file so verification codes can be read without external email credentials.

## Synthetic reservation email simulation

Local reservation communication scenarios may use addresses under `example.test` only when the runtime is explicitly isolated: `APP_ENV=development`, `EMAIL_PROVIDER=null`, `EXTERNAL_EFFECTS_ENABLED=false`, and `CONNECTIONS_ENABLED=false` (or in test mode). A send attempt for one of these reserved addresses is recorded as failed with an explicit no-email-sent reason and returns before any email provider is called. These attempts are not written to the verification-code outbox. Production, preview, and QA runtimes reject `example.test` addresses.

For local scenarios that also need currency conversion, `DOLARAPI_RATES_ENABLED=true` allows only public, read-only quote requests; it does not enable payment, email, OTA, or other provider traffic. Keep the two external-effects flags above set to `false`. The PMS stores shared public rates in PostgreSQL and reuses a quote received within the last three hours, so reservation estimates and payment previews do not call DolarAPI on every view. After that cache window expires, the next conversion attempts a live refresh and stores a valid response. A scheduled task also refreshes supported rates daily at 08:00 in `HOTEL_TIMEZONE`. If DolarAPI is unreachable, the last response received by the PMS can support conversion for at most 24 hours from `observed_at`; the UI warns when using this outage fallback. After that window, automatic cross-currency conversion is blocked. An authorized user can set a one-time, audited amount for a specific reservation; a user with payment-collection permission can then record that exact amount. Run the `20261029_fx_rate_cache` Alembic migration before starting the updated app.

## Recommended local startup

```bash
export APP_ENV=development
export TESTING=true
export DEV_EMAIL_OUTBOX_PATH="$PWD/tmp/dev-email-outbox.jsonl"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8040
```

## Staging handoff

Before staging, make sure the backend is restarted after any config change and that the active process is serving the current `app/services/onboarding_service.py` and `app/master_admin/email_provider.py` code.
