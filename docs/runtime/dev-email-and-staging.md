# Dev email and staging runtime

## Development email minimum

For local validation of `register-owner -> verify-email -> onboarding/status`, the backend should run with:

- `APP_ENV=development`
- `TESTING=true`
- `DEV_EMAIL_OUTBOX_PATH=<workspace>/tmp/dev-email-outbox.jsonl` or leave empty to use the system temp fallback

In development and non-production modes, transactional email is captured as a dev no-op and written to the outbox file so verification codes can be read without external email credentials.

## Synthetic reservation email simulation

Local reservation communication scenarios may use addresses under `example.test` only when the runtime is explicitly isolated: `APP_ENV=development`, `EMAIL_PROVIDER=null`, `EXTERNAL_EFFECTS_ENABLED=false`, and `CONNECTIONS_ENABLED=false` (or in test mode). A send attempt for one of these reserved addresses is recorded as failed with an explicit no-email-sent reason and returns before any email provider is called. These attempts are not written to the verification-code outbox. Production, preview, and QA runtimes reject `example.test` addresses.

For local scenarios that also need currency conversion, `DOLARAPI_RATES_ENABLED=true` allows only public, read-only quote requests; it does not enable payment, email, OTA, or other provider traffic. Keep the two external-effects flags above set to `false`.

## Recommended local startup

```bash
export APP_ENV=development
export TESTING=true
export DEV_EMAIL_OUTBOX_PATH="$PWD/tmp/dev-email-outbox.jsonl"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8040
```

## Staging handoff

Before staging, make sure the backend is restarted after any config change and that the active process is serving the current `app/services/onboarding_service.py` and `app/master_admin/email_provider.py` code.
