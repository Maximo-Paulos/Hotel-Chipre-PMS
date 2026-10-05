# Analytics R1.0

Analytics R1.0 is the hotel-scoped analytics module for Hotel-Chipre-PMS.
It uses `hotel_configuration.id` as the canonical hotel identifier and keeps all analytics data isolated per hotel.

## Overview

The module provides:

- a starter landing summary for `starter`
- full analytics for `pro`
- full analytics plus XLSX async exports, IA analytics, alert settings and snoozes for `ultra`
- company CRUD
- room state events
- nightly reservation and occupancy facts
- exports, observability, and AI-assisted insights bounded to the hotel domain

## Tiers

- `starter`
  - can access `/analytics`
  - sees the starter landing summary
  - cannot access the full analytics module
  - cannot access exports or IA
- `pro`
  - can access the full analytics module
  - can use PNG and CSV sync exports
  - cannot use XLSX async exports
  - cannot use IA analytics
  - cannot manage alert settings or snoozes
- `ultra`
  - can access the full analytics module
  - can use PNG and CSV sync exports
  - can use XLSX async exports
  - can use IA analytics
  - can manage alert settings and snoozes

## Main endpoints

### Analytics reports

- `GET /api/analytics/starter-summary`
- `GET /api/analytics/home`
- `GET /api/analytics/rooms`
- `GET /api/analytics/rooms/{room_id}`
- `GET /api/analytics/categories/{category_id}`
- `GET /api/analytics/segments`
- `GET /api/analytics/companies/{company_id}`
- `GET /api/analytics/channels`
- `GET /api/analytics/operations`

### Alert settings

- `GET /api/analytics/alert-settings`
- `PATCH /api/analytics/alert-settings`
- `POST /api/analytics/alerts/{alert_code}/snooze`
- `DELETE /api/analytics/alerts/{alert_code}/snooze`

### AI config and insights

- `GET /api/analytics/ai-config`
- `PATCH /api/analytics/ai-config`
- `GET /api/analytics/insights/status`
- `POST /api/analytics/insights/home`
- `POST /api/analytics/insights/anomalies`
- `POST /api/analytics/insights/pricing`

### Companies and room events

- `GET /api/companies`
- `POST /api/companies`
- `GET /api/companies/{company_id}`
- `PATCH /api/companies/{company_id}`
- `POST /api/companies/{company_id}/deactivate`
- `POST /api/companies/{company_id}/reactivate`
- `GET /api/room-state-events`
- `POST /api/room-state-events`
- `POST /api/room-state-events/{event_id}/close`

### Exports

- `POST /api/analytics/exports/png`
- `POST /api/analytics/exports/csv`
- `POST /api/analytics/exports/xlsx`
- `GET /api/analytics/exports`
- `GET /api/analytics/exports/{job_id}`
- `GET /api/analytics/exports/{job_id}/download`

PNG and CSV are synchronous.
Only XLSX creates a job row in `analytics_export_jobs`.

## Jobs and facts

- `analytics.detect_no_shows`
- `analytics.refresh_fact_reservation_daily`
- `analytics.refresh_fact_room_occupancy_daily`
- `analytics.cleanup_expired_exports`

Facts are hotel-scoped and use the canonical contracts established in the core services layer.

Reservation mutations refresh their affected PostgreSQL fact windows in the
same transaction. Analytics reads can repair a missing or aged fact window
when `SYNC_FACT_REFRESH_ENABLED=true` (default) and the entire requested range
is no wider than `SYNC_FACT_REFRESH_MAX_DAYS` (default 31, hard-capped at 31).
An existing window is considered aged after
`SYNC_FACT_REFRESH_STALE_AFTER_SECONDS` (default 900 seconds). Wider custom
date ranges are never partially rebuilt on each read; their `data_as_of` and
`source_lag_seconds` continue to report the oldest materialized row honestly.
These fields describe fact materialization time, not a separate watermark of
source-table writes. ClickHouse projection schedules are a distinct pipeline
and do not refresh the PostgreSQL reservation and occupancy fact tables.

Reservation totals are allocated over the complete stay before a requested date window is selected. Partial or repeated refreshes therefore preserve the same nightly amounts independent of refresh order. `ADR` is PMS net room revenue over chargeable occupied nights; `RevPAR` is PMS net room revenue over sellable room nights. When a source currency cannot be converted with its saved FX snapshot, analytics tables mark that target currency unavailable instead of presenting zero as a real converted amount.

Financial report booked value includes stays overlapping the selected local hotel dates and allocates the contractual total evenly over the stay nights before summing the selected nights. Collected payments and refunds remain grouped by the tender currency; analytics and reports do not infer an FX rate.

To rebuild historical reservation and occupancy facts after an allocation fix, use the idempotent command `python scripts/repair_analytics_facts.py --hotel-id <id>` or `python scripts/repair_analytics_facts.py --all-hotels`. Optional `--date-from YYYY-MM-DD --date-to YYYY-MM-DD` flags restrict the rebuilt interval. The command commits one hotel at a time and never prints guest or payment details.

Preview the exact hotel/date scopes and aggregate row counts before rebuilding by adding `--dry-run`, for example `python scripts/repair_analytics_facts.py --all-hotels --dry-run`. The report includes overlapping reservation counts, existing fact rows that would be replaced, and the estimated occupancy rows to generate; it never writes or prints reservation details. Run an applying command only after reviewing the report and confirming the configured database is the intended isolated environment.

Rate, surcharge, and room-status audit records are inserted in the same SQL transaction as their business mutation. These paths fail the request if the audit insert fails; the caller owns the commit.

## Dashboard Analytics and IA chat

The Analytics dashboard and the Analytics IA chat are separate experiences.
The dashboard must keep loading metrics, drill-downs, filters, comparators and exports even when the IA provider is disabled or missing configuration.

- Dashboard route: `/analytics` plus drill-down routes under `/analytics/*`.
- IA chat route: `/analytics/ai-chat`.
- IA chat API: `POST /api/analytics/ai-chat`.

If IA is not connected, the chat screen remains available for `ultra` users and the backend returns:

- `{"detail":"La IA todavía no está conectada. Configurá el proveedor de IA para usar el asistente."}`

The dashboard does not depend on `AI_ENABLED`, `AI_API_KEY`, `AI_BASE_URL` or any provider runtime state.

## IA analytics

Analytics IA uses a provider abstraction behind the Analytics service layer.
The backend selects the provider from environment configuration, so deploys can switch between a self-hosted Gemma/OpenAI-compatible runtime and an external OpenAI-compatible API without changing Analytics code.

Rules:

- no general-purpose free-form chat
- existing insight endpoints stay limited to `home`, `anomalies`, and `pricing`
- the dedicated IA chat only accepts hotel Analytics domain questions
- no arbitrary prompt field in Analytics insight requests
- no direct SQL or database access for the model
- model input is a curated hotel-scoped context built by the backend
- no silent mutation of critical hotel data
- monthly quota tracked per hotel

Provider options:

- `AI_PROVIDER=gemma`: use a self-hosted OpenAI-compatible endpoint, for example Ollama or a rig-local gateway.
- `AI_PROVIDER=openai`: use an external OpenAI-compatible API endpoint. If `AI_BASE_URL` is empty, the backend uses `https://api.openai.com/v1/chat/completions`.
- legacy `GEMMA_*` variables still work as fallback values for compatibility with the global Gemma assistant.

## Filters

Analytics screens persist filters in `sessionStorage` using the key:

- `analytics:filters:{hotel_id}:{route_name}`

Stored fields:

- `date_from`
- `date_to`
- `currency_display`
- `compare_previous`
- `compare_yoy`

Default values:

- `date_from`: first day of the current local month
- `date_to`: today in local time
- `currency_display`: `ARS`
- `compare_previous`: `true`
- `compare_yoy`: `false`

## Release gate

Analytics R1.0 is considered complete when:

- schema and models match the final contract
- core contracts and services are in place
- facts and jobs run
- backend endpoints exist and enforce tier gating
- exports and IA work as specified
- frontend analytics routes and screens are wired
- filter persistence is in place
- the Analytics-focused validation suite passes

## Operational notes

- Hotel scoping is always resolved from the real hotel context in the app.
- Errors use the repo's existing `{"detail":"..."}` pattern.
- The module is designed to stay hotel-safe and avoid cross-hotel leakage.

## Deployment checklist

Required environment:

- `DATABASE_URL`
- `ANALYTICS_EXPORTS_DIR`
- `AI_ENABLED`
- `AI_PROVIDER`
- `AI_BASE_URL`
- `AI_API_KEY`
- `AI_MODEL`
- `AI_TIMEOUT_SECONDS`
- `AI_MAX_OUTPUT_TOKENS`
- `AI_TEMPERATURE`
- `AI_STRICT_JSON`
- `AI_MONTHLY_QUOTA`
- `RESEND_API_KEY`

Migration command:

- `alembic upgrade head`

Runtime jobs:

- `analytics.detect_no_shows`
- `analytics.refresh_fact_reservation_daily`
- `analytics.refresh_fact_room_occupancy_daily`
- `analytics.cleanup_expired_exports`

Storage:

- `ANALYTICS_EXPORTS_DIR` must exist or be creatable by the worker process.
- XLSX files are stored under `{ANALYTICS_EXPORTS_DIR}\{hotel_id}\{YYYY}\{MM}\{job_id}.xlsx`.
- The directory must not be exposed via static hosting.

Post-deploy checks:

- `GET /health`
- `GET /api/analytics/starter-summary`
- `GET /api/analytics/home`
- `GET /api/analytics/rooms`
- `GET /api/analytics/alert-settings`
- `GET /api/analytics/ai-config`
- `GET /api/companies`
- create and close a room state event
- create an XLSX export and download it
- verify Analytics tier gating for starter/pro/ultra
