# Architecture Audit

## What exists today

### Backend
- `app/main.py` is the FastAPI entrypoint and also serves the built frontend.
- Thin routers live in `app/api/`.
- Business logic lives mainly in `app/services/`.
- Domain models live in `app/models/`.
- Database setup and settings live in `app/database.py` and `app/config.py`.
- Migrations live in `alembic/`.
- Background work exists in `app/tasks/` through Celery.

### Frontend
- The frontend is a Vite + React + TypeScript app under `frontend/src/`.
- Routing is centralized in `frontend/src/router.tsx`.
- Session and API context are handled in `frontend/src/state/` and `frontend/src/api/`.
- The protected UI includes dashboard, guests, reservations, rooms, and settings pages.

### Core product areas already present
- Reservations, guests, rooms, check-in, payments, onboarding, integrations, subscriptions, auth.
- OTA intake and foundation models.
- Allocation engine, allocation policy, and allocation runtime.
- Gemma assistant, insights, and controlled action previews.
- Commercial and pricing flows used by reservation operations.

## Graphify signal
- The codebase is large enough that graph structure matters.
- Main hotspots are reservation state, room allocation, OTA integration, and Gemma-assisted workflows.
- God nodes are mostly reservation, room, configuration, and status enums.

## Current gaps visible in the repo
- OTA lifecycle is not yet fully closed operationally.
- Allocation still needs stronger pilot behavior around gaps, manual review, and operator control.
- Guest and check-in UX is not yet a full first-class workflow.
- Gemma is intentionally bounded and still needs a tighter feedback/runtime loop.

## Local efficiency and scale findings (2026-10-15)

The latest local-only review and its coverage ledger are in [Auditoría local de eficiencia, capacidad y reglas operativas](audits/auditoria-eficiencia-capacidad-y-reglas-operativas-2026-10-15.md).

- Keep FastAPI, React/Vite, SQLAlchemy and PostgreSQL. The workload evidence does not justify a framework rewrite, Redis, another source-of-truth database, or warehouse for the pilot.
- PostgreSQL remains authoritative. Existing code has removed the repeated short-interval outbox and UI polling, grouped high-volume summary reads, bounded detail pages, and reduced redundant optimizer work. Keep those changes; measure regressions before adding caches or indexes.
- Current realtime/collaboration has process-local coordination. Do not scale API replicas/workers horizontally until shared coordination and duplicate delivery behavior are measured and made safe.
- XLSX exports use one sequential in-process worker and recover unexpired jobs on startup for a single local instance, provided PostgreSQL and `OBJECT_STORAGE_LOCAL_DIR` persist. This is not multi-instance coordination.
- A synthetic local HTTP run at up to about 100 requests/second completed with no HTTP errors, but the 500-user case briefly reached about one local CPU core and the gradual 500-stream test used about 433 MiB RSS. These results are workload-specific and are not a managed-hosting guarantee.
- The Vite build reports a 572 kB initial JavaScript chunk. Keep it as a frontend optimization candidate; split only after a browser bundle/route-load measurement demonstrates useful improvement.
- This review used no cloud account, remote database, deployment or provider telemetry. Hosting prices and provider-side limits therefore remain unverified.

