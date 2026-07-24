# Hotel Chipre PMS - Deploy Guide

Arquitectura objetivo:
- Frontend/landing/app: Vercel
- Backend API: Render
- Base de datos: Supabase
- DNS: Cloudflare

## 1) Vercel

Crear un proyecto desde la raíz del repo.

Config:
- Framework: Vite
- No usar `FastAPI` como framework preset para este proyecto de Vercel.
- Build command: usar la del `vercel.json` de la raíz
- Output directory: `frontend/dist`
- Rewrites SPA: todas las rutas a `/index.html`
- Si el proyecto de Vercel usa `Root Directory = frontend`, la config equivalente vive en `frontend/vercel.json`.

Dominios a conectar:
- `hotels-pms.com`
- `app.hotels-pms.com`

Variables de entorno:
- `VITE_API_URL=https://<render-service>.onrender.com/api`
- `VITE_PUBLIC_SITE_URL=https://hotels-pms.com`
- `VITE_PUBLIC_APP_URL=https://app.hotels-pms.com`
- `VITE_PUBLIC_APP_HOSTNAME=app.hotels-pms.com`
- `VITE_ALLOW_INDEXING=true` en production

## 2) Render

Crear un Web Service desde `render.yaml`.

Config del servicio:
- Build command: `pip install -r requirements.txt`
- Start command: `python -m alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- Healthcheck: `/health`

Regla de esquema:
- Producción, preview, QA y staging deben ejecutar Alembic antes de iniciar la aplicación.
- El backend falla cerrado si PostgreSQL no tiene `alembic_version` con una revisión aplicada.
- `create_all()` queda reservado para desarrollo/tests locales; no se usa para reparar drift en un deploy.
- Cuando el proveedor permita un release/pre-deploy job separado, ejecutar allí `alembic upgrade head` y dejar el proceso web sólo con Uvicorn.

Variables de entorno:
- `APP_ENV=production`
- `DATABASE_URL=postgresql+psycopg2://...` (Supabase)
- `APP_BASE_URL=https://<render-service>.onrender.com`
- `FRONTEND_URL=https://app.hotels-pms.com`
- `CORS_ORIGINS=https://hotels-pms.com,https://app.hotels-pms.com`
- `JWT_SECRET=<strong secret>`
- `MANAGER_PIN=<6+ digits>`
- `INTEGRATIONS_ENCRYPTION_KEY=<fernet key>`
- `EMAIL_PROVIDER=resend`
- `RESEND_API_KEY=<resend key>`
- `SYSTEM_EMAIL_FROM="Hotel Chipre PMS <noreply@auth.hotels-pms.com>"`
- `SYSTEM_EMAIL_REPLY_TO=hotelxpms@gmail.com`
- `ANALYTICS_EXPORTS_DIR=/var/exports/analytics`
- Transfer-proof bytes are stored in the private `payment_proof_blobs` table; expose them only through the authenticated, tenant-scoped proof endpoint.
- `AI_ENABLED=false` until the hotel-specific IA provider is configured
- `GEMMA_ENABLED=false`

## 3) Cloudflare DNS

Primero cambiar los nameservers del dominio al set de Cloudflare.

Luego crear:
- `@` -> CNAME flattening al target que entrega Vercel para el proyecto
- `app` -> CNAME al target que entrega Vercel para el mismo proyecto
- `api` -> opcional, CNAME al target que entrega Render si querés vanity API

Notas:
- Los targets exactos no se pueden deducir del repo. Copiar los valores que muestren Vercel/Render en sus dashboards.
- Si Vercel o Render piden TXT de verificación, copiar exactamente el que indiquen.

## 4) Qué validar después

- `https://hotels-pms.com/`
- `https://hotels-pms.com/precios`
- `https://hotels-pms.com/funciones`
- `https://hotels-pms.com/pms-hotelero`
- `https://hotels-pms.com/software-para-hoteles`
- `https://hotels-pms.com/faq`
- `https://app.hotels-pms.com/login`
- `https://app.hotels-pms.com/register-owner`
- `GET https://<render-service>.onrender.com/health`
- Flujo de auth:
  - register
  - verify email
  - onboarding/status

## 5) Errores típicos

- DNS no resuelto: nameservers o CNAME mal puestos
- CORS error: `CORS_ORIGINS` incorrecto en Render
- Links de email rotos: `FRONTEND_URL` no apunta a `app.hotels-pms.com`
- Frontend hablando con localhost: `VITE_API_URL` no configurado en Vercel
- Email fallando al arrancar: falta `RESEND_API_KEY` o `SYSTEM_EMAIL_FROM`
- SPA 404 en rutas internas: rewrites de Vercel ausentes o proyecto equivocado
