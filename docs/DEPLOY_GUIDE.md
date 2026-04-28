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
- Build command: usar la del `vercel.json` de la raíz
- Output directory: `frontend/dist`
- Rewrites SPA: todas las rutas a `/index.html`

Dominios a conectar:
- `hoteles-pms.com`
- `app.hoteles-pms.com`

Variables de entorno:
- `VITE_API_URL=https://<render-service>.onrender.com/api`
- `VITE_PUBLIC_SITE_URL=https://hoteles-pms.com`
- `VITE_PUBLIC_APP_URL=https://app.hoteles-pms.com`
- `VITE_PUBLIC_APP_HOSTNAME=app.hoteles-pms.com`
- `VITE_ALLOW_INDEXING=true` en production

## 2) Render

Crear un Web Service desde `render.yaml`.

Config del servicio:
- Build command: `pip install -r requirements.txt`
- Start command: `python -m alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- Healthcheck: `/health`

Variables de entorno:
- `APP_ENV=production`
- `DATABASE_URL=postgresql+psycopg2://...` (Supabase)
- `APP_BASE_URL=https://<render-service>.onrender.com`
- `FRONTEND_URL=https://app.hoteles-pms.com`
- `CORS_ORIGINS=https://hoteles-pms.com,https://app.hoteles-pms.com`
- `JWT_SECRET=<strong secret>`
- `MANAGER_PIN=<6+ digits>`
- `INTEGRATIONS_ENCRYPTION_KEY=<fernet key>`
- `EMAIL_PROVIDER=resend`
- `RESEND_API_KEY=<resend key>`
- `SYSTEM_EMAIL_FROM="Hotel Chipre PMS <noreply@auth.hoteles-pms.com>"`
- `SYSTEM_EMAIL_REPLY_TO=hotelxpms@gmail.com`
- `ANALYTICS_EXPORTS_DIR=/var/exports/analytics`
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

- `https://hoteles-pms.com/`
- `https://hoteles-pms.com/precios`
- `https://hoteles-pms.com/funciones`
- `https://hoteles-pms.com/pms-hotelero`
- `https://hoteles-pms.com/software-para-hoteles`
- `https://hoteles-pms.com/faq`
- `https://app.hoteles-pms.com/login`
- `https://app.hoteles-pms.com/register-owner`
- `GET https://<render-service>.onrender.com/health`
- Flujo de auth:
  - register
  - verify email
  - onboarding/status

## 5) Errores típicos

- DNS no resuelto: nameservers o CNAME mal puestos
- CORS error: `CORS_ORIGINS` incorrecto en Render
- Links de email rotos: `FRONTEND_URL` no apunta a `app.hoteles-pms.com`
- Frontend hablando con localhost: `VITE_API_URL` no configurado en Vercel
- Email fallando al arrancar: falta `RESEND_API_KEY` o `SYSTEM_EMAIL_FROM`
- SPA 404 en rutas internas: rewrites de Vercel ausentes o proyecto equivocado
