#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Render startup script
# Runs Alembic migrations to head, then starts uvicorn.
# Render sets $PORT automatically; we honour it here.
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo "==> Running Alembic migrations..."
python -m alembic upgrade head

echo "==> Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
