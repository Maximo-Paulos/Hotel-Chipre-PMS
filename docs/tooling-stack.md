# Tooling Stack

## Backend
- Python 3.11+
- FastAPI
- SQLAlchemy
- Alembic
- Uvicorn
- Pytest
- Celery
- Redis
- OR-Tools
- httpx
- psycopg2-binary

## Frontend
- Node 20+
- React 18
- TypeScript
- Vite
- TanStack Query
- React Router
- Tailwind CSS
- ESLint
- Playwright

## Repo-level runtime
- `nodemon.json` runs the backend with reload in local development.
- `docker-compose.yml` defines Postgres, backend, and frontend services.
- The backend serves the built frontend from `frontend/dist` when present.

## Common commands
- Backend tests: `pytest`
- Frontend build: `cd frontend && npm run build`
- Frontend lint: `cd frontend && npm run lint`
- Frontend e2e: `cd frontend && npm run e2e`

