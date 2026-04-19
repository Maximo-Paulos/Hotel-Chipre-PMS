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

