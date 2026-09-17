---
name: dev-up
description: Start the local development environment for Hotel Chipre PMS on macOS — backend API, frontend dev server, and optional Redis — with the correct venv/node paths and ports. Use when the user asks to "levantar", "arrancar el entorno", "correr local", or run the app locally.
---

# dev-up — arrancar el entorno local (macOS)

Este entorno se montó sin brew/Docker: Python 3.12 en `.venv/`, Node 20 en `~/.local/node`,
Redis compilado en `~/.local/bin`. Rutas y puertos importan.

## Backend (FastAPI, puerto 8040)
```sh
cd "$(git rev-parse --show-toplevel)"
# migraciones (usa DATABASE_URL de .env; por defecto SQLite local)
.venv/bin/python -m alembic upgrade head
# servidor con reload
.venv/bin/python -m uvicorn app.main:app --reload --port 8040
```
Health: `GET http://127.0.0.1:8040/health`. Mutaciones necesitan header `X-Hotel-Id`.
El puerto es 8040, no 8000: es lo que esperan el proxy de `vite.config.mjs`, `frontend/.env.local`
y `nodemon.json`. Con el backend en 8000 el frontend se levanta pero no llega a la API.

## Frontend (Vite, puerto 5173)
```sh
export PATH="$HOME/.local/node/bin:$PATH"
cd "$(git rev-parse --show-toplevel)/frontend"
npm run dev          # http://127.0.0.1:5173
```
El dev server espera la API según `VITE_API_URL`.

## Redis (opcional — Celery / sync OTA)
```sh
export PATH="$HOME/.local/bin:$PATH"
redis-server --daemonize yes            # apagar: redis-cli shutdown nosave
```
Sólo hace falta si vas a ejercitar Celery/OTA; la app arranca sin él.

## e2e (Playwright)
Activá el venv primero para que el webServer tome el Python correcto:
```sh
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
export PATH="$HOME/.local/node/bin:$PATH"
cd frontend && npm run e2e
```

## Nota de deploy
Prod corre en Render (backend) + Vercel (frontend) + Supabase (DB). No necesitás Docker
local; deployás con `git push` a `main` (Render tiene autoDeploy y corre las migraciones al arrancar).
