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
- Ruff (pinned in `requirements-lint.txt`, initially limited to undefined-name checks)

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
- Install Python lint tool: `python -m pip install -r requirements-lint.txt`
- Python undefined-name check: `python -m ruff check app scripts alembic tests --select F821 --target-version py311`
- Frontend build: `cd frontend && npm run build`
- Frontend lint: `cd frontend && npm run lint`
- Frontend e2e: `cd frontend && npm run e2e`

