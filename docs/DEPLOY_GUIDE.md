# Hotel Chipre PMS — Guía de Deploy

> **Arquitectura objetivo:** Supabase (PostgreSQL) + Render (backend FastAPI) + Vercel (frontend React)
>
> **Lo que ya está hecho en el repo:** toda la configuración de archivos (`render.yaml`, `vercel.json`, `start.sh`, `Procfile`). Vos solo tenés que crear las cuentas, copiar credenciales y pegar variables de entorno.

---

## Índice

1. [Prereqs](#1-prereqs)
2. [Supabase — base de datos](#2-supabase--base-de-datos)
3. [Render — backend](#3-render--backend)
4. [Vercel — frontend](#4-vercel--frontend)
5. [Wiring: conectar las tres partes](#5-wiring-conectar-las-tres-partes)
6. [Variables manuales — resumen completo](#6-variables-manuales--resumen-completo)
7. [Verificación post-deploy](#7-verificación-post-deploy)
8. [Troubleshooting](#8-troubleshooting)
9. [Tareas automáticas vs manuales](#9-tareas-automáticas-vs-manuales)

---

## 1. Prereqs

| Cuenta | URL | Plan gratuito |
|--------|-----|---------------|
| Supabase | https://supabase.com | Sí (500 MB DB) |
| Render | https://render.com | Sí (se duerme tras 15 min inactividad) |
| Vercel | https://vercel.com | Sí (ilimitado para frontends estáticos) |
| GitHub | https://github.com | Sí — el repo debe estar pusheado aquí |

> **Importante sobre Render free tier:** El servicio "se duerme" tras 15 minutos sin requests. El primer request tras despertar tarda ~30s. Para demo está bien; para producción real, actualizar a Starter ($7/mes) o usar Railway.

---

## 2. Supabase — base de datos

### 2.1 Crear el proyecto

1. Entrar a https://supabase.com → **New project**
2. Elegir nombre (ej. `hotel-chipre-pms`), región (ej. `South America (São Paulo)`), password para la DB
3. **Guardar el password** — no se puede recuperar después
4. Esperar ~2 minutos a que el proyecto se inicialice

### 2.2 Obtener la connection string

1. En el dashboard del proyecto → **Project Settings** (ícono de engranaje) → **Database**
2. Bajar hasta **Connection string** → seleccionar tab **URI**
3. Copiar la URL. Tiene el formato:
   ```
   postgresql://postgres:[TU-PASSWORD]@db.[REF].supabase.co:5432/postgres
   ```
4. **Convertir para SQLAlchemy** — cambiar el prefijo a `postgresql+psycopg2`:
   ```
   postgresql+psycopg2://postgres:[TU-PASSWORD]@db.[REF].supabase.co:5432/postgres
   ```

> **Por qué puerto 5432 y no 6543:**
> El puerto 6543 es el pooler en modo Transaction. Alembic necesita ejecutar DDL (CREATE TABLE, ALTER TABLE) que **no es compatible** con el pooler en modo transaction. Usar siempre el puerto 5432 (conexión directa) para el `DATABASE_URL` en Render.

### 2.3 Configurar IPv4 (si Render lo requiere)

Render free tier puede conectarse solo vía IPv4. Supabase en el plan gratuito expone IPv4 para conexiones directas. Si ves errores de conexión, verificar en **Project Settings → Network → IPv4 address**.

### 2.4 Deshabilitar Row Level Security (RLS) — opcional

Si la app no usa las políticas RLS de Supabase (no las usa — maneja auth propio), asegurarse de que las tablas **no tengan RLS** activo. Alembic crea las tablas sin RLS por defecto; no hacer nada extra.

---

## 3. Render — backend

### 3.1 Crear el servicio

1. Entrar a https://render.com → **New** → **Web Service**
2. Conectar tu repositorio de GitHub
3. Configurar:
   - **Name:** `hotel-chipre-pms-api`
   - **Branch:** `main`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt` *(ya en render.yaml)*
- **Start Command:** `python -m alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` *(ya en render.yaml)*
   - **Plan:** Free

> Render detecta `render.yaml` automáticamente si lo conectás via **Blueprint**. En ese caso: **New → Blueprint** en lugar de **Web Service**.

### 3.2 Variables de entorno en Render

En el dashboard del servicio → **Environment** → agregar cada variable:

| Variable | Valor | Cómo obtenerlo |
|----------|-------|----------------|
| `DATABASE_URL` | `postgresql+psycopg2://postgres:[pass]@db.[ref].supabase.co:5432/postgres` | Supabase > Project Settings > Database |
| `JWT_SECRET` | *(generado automático por render.yaml)* | Render lo genera; o generá uno: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `APP_BASE_URL` | `https://hotel-chipre-pms-api.onrender.com` | La URL que Render te asigna al servicio |
| `CORS_ORIGINS` | `https://hotel-chipre.vercel.app` | La URL de tu app en Vercel (paso 4) |
| `FRONTEND_URL` | `https://hotel-chipre.vercel.app` | La misma URL de Vercel (para links en emails) |
| `MASTER_ADMIN_EMAIL` | `owner-admin@tu-dominio.com` | Usuario bootstrap del panel master |
| `MASTER_ADMIN_PASSWORD` | `...` | Contraseña bootstrap del panel master |
| `MASTER_ADMIN_PIN` | `XXXXXX` | Mínimo 6 dígitos, NO usar 1234 |
| `INTEGRATIONS_ENCRYPTION_KEY` | *(output del comando de abajo)* | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `GOOGLE_OAUTH_REDIRECT_URI` | `https://[TU-SERVICIO].onrender.com/api/master-admin/email/oauth/gmail/callback` | Callback OAuth del mail del sistema |
| `GOOGLE_OAUTH_CLIENT_ID` | `...` | Google Cloud OAuth client |
| `GOOGLE_OAUTH_CLIENT_SECRET` | `...` | Google Cloud OAuth client |
| `GEMMA_ENABLED` | `false` | *(ya en render.yaml)* |

> **El mail del sistema ya no usa SMTP ni app passwords.** Se conecta desde `/adminpmsmaster` con Gmail OAuth y el backend persiste esa conexión de forma segura.

> **Integraciones opcionales:** Mercado Pago, PayPal y Gmail OAuth solo se validan cuando realmente se cargan sus credenciales en producción. Si no las vas a usar en el piloto, dejalas vacías.

### 3.3 Lo que hace el Start Command automáticamente

```bash
python -m alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
```

**No tenés que crear las tablas manualmente en Supabase.** Alembic las crea en el primer deploy.

### 3.4 Verificar que levantó

```
GET https://hotel-chipre-pms-api.onrender.com/health
# Debe retornar: {"status": "ok", "system": "Hotel PMS v1.0.0"}
```

---

## 4. Vercel — frontend

### 4.1 Crear el proyecto

1. Entrar a https://vercel.com → **Add New Project**
2. Importar el repositorio de GitHub
3. Vercel detecta `vercel.json` automáticamente

La configuración en `vercel.json` ya define:
- **Build Command:** `cd frontend && npm install && npm run build`
- **Output Directory:** `frontend/dist`
- **Rewrites:** todas las rutas van a `index.html` (SPA routing)
- **Cache headers:** assets estáticos con 1 año de cache

### 4.2 Variables de entorno en Vercel

En el dashboard del proyecto → **Settings** → **Environment Variables**:

| Variable | Valor | Entornos |
|----------|-------|---------|
| `VITE_API_URL` | `https://hotel-chipre-pms-api.onrender.com/api` | Production, Preview |

> **Importante:** El nombre debe ser `VITE_API_URL` exactamente. Vite solo expone al bundle las variables que empiezan con `VITE_`. Sin esta variable, el frontend intentará conectarse a `http://127.0.0.1:8040/api` y fallará en producción.

### 4.3 Redeploy tras agregar la variable

Después de agregar `VITE_API_URL`, hacer **Redeploy** desde el dashboard de Vercel (el build inicial no la tendrá).

---

## 5. Wiring: conectar las tres partes

El orden importa:

```
1. Crear Supabase → copiar DATABASE_URL
2. Crear Render → pegar DATABASE_URL → Render te da su URL (onrender.com)
3. Crear Vercel → Vercel te da su URL (vercel.app)
4. Volver a Render → pegar CORS_ORIGINS y FRONTEND_URL con la URL de Vercel
5. Volver a Vercel → pegar VITE_API_URL con la URL de Render → Redeploy
```

### Diagrama de URLs cruzadas

```
Vercel (frontend)          Render (backend)          Supabase (DB)
vercel.app    ──VITE_API_URL──▶  onrender.com    ──DATABASE_URL──▶  supabase.co
              ◀──CORS_ORIGINS──  (configurado en Render env)
              ◀──FRONTEND_URL──  (para links en emails de invitación)
```

---

## 6. Variables manuales — resumen completo

Variables que **sí se configuran en el repo** (`render.yaml`):
- `APP_ENV=production`
- `GEMMA_ENABLED=false`
- `JWT_SECRET` (Render lo genera automáticamente con `generateValue: true`)

Variables que **vos pegás manualmente** en el dashboard de Render:

```
DATABASE_URL                = postgresql+psycopg2://postgres:[PASS]@db.[REF].supabase.co:5432/postgres
APP_BASE_URL                = https://[TU-SERVICIO].onrender.com
CORS_ORIGINS                = https://[TU-APP].vercel.app
FRONTEND_URL                = https://[TU-APP].vercel.app
MASTER_ADMIN_EMAIL           = [EMAIL DEL OWNER MASTER]
MASTER_ADMIN_PASSWORD        = [PASSWORD DEL OWNER MASTER]
MASTER_ADMIN_PIN             = [MINIMO 6 DIGITOS, NO 1234]
INTEGRATIONS_ENCRYPTION_KEY = [OUTPUT DE: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"]
GOOGLE_OAUTH_REDIRECT_URI   = https://[TU-SERVICIO].onrender.com/api/master-admin/email/oauth/gmail/callback
GOOGLE_OAUTH_CLIENT_ID      = [OAuth client id de Google]
GOOGLE_OAUTH_CLIENT_SECRET  = [OAuth client secret de Google]
```

Variables que **vos pegás manualmente** en el dashboard de Vercel:

```
VITE_API_URL       = https://[TU-SERVICIO].onrender.com/api
```

---

## 7. Verificación post-deploy

### Backend (Render)

```bash
# 1. Health check
curl https://TU-SERVICIO.onrender.com/health
# Esperado: {"status":"ok","system":"Hotel PMS v1.0.0"}

# 2. Docs (solo en APP_ENV != production con --reload, o si no deshabilitaste /docs)
# GET https://TU-SERVICIO.onrender.com/docs

# 3. Login
curl -X POST https://TU-SERVICIO.onrender.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"TU@EMAIL.COM","password":"TU-PASSWORD"}'
# Esperado: {"access_token":"...","token_type":"bearer"}
```

### Frontend (Vercel)

1. Abrir `https://TU-APP.vercel.app`
2. Hacer login con el usuario existente
3. Verificar que las reservas cargan (confirma que `VITE_API_URL` apunta al backend correcto)

### Checklist de smoke test

- [ ] `GET /health` retorna 200
- [ ] Login devuelve token JWT
- [ ] Frontend carga sin errores de CORS en consola del browser
- [ ] Dashboard muestra datos del hotel (no error 401/403)
- [ ] Crear una reserva de prueba

---

## 8. Troubleshooting

### "CORS error" en el browser

- Verificar que `CORS_ORIGINS` en Render contiene la URL exacta de Vercel (con `https://`, sin trailing slash)
- Render + Vercel: el regex `https://.*\.vercel\.app` ya está hardcodeado en `app/main.py` — cualquier URL `.vercel.app` pasa CORS automáticamente

### "Connection refused" o timeout al conectar a Supabase

- Verificar que `DATABASE_URL` usa puerto **5432** (directo), no 6543
- Verificar que el password no tiene caracteres especiales que rompan la URL (encodear si es necesario: `@` → `%40`, `#` → `%23`)

### "Invalid production security configuration"

El backend lanza este error si detecta secrets inseguros en modo producción. Verificar:
- `JWT_SECRET` tiene al menos 32 caracteres
- `MASTER_ADMIN_PIN` tiene al menos 6 dígitos y no es `1234`
- `APP_BASE_URL` empieza con `https://` y no tiene `localhost`
- Las URLs de redirect y `MERCADOPAGO_WEBHOOK_SECRET` solo se exigen si la integración correspondiente está activada con credenciales reales

### Alembic falla en el startup

Ver los logs de Render. Causas comunes:
- `DATABASE_URL` incorrecto (credenciales o host mal copiado)
- Supabase aún inicializando (esperar 2-3 minutos y redeploy)
- `psycopg2-binary` no puede conectar — verificar IPv4 en Supabase

### Frontend muestra datos de localhost

- `VITE_API_URL` no está seteada en Vercel → el frontend usa el default `http://127.0.0.1:8040/api`
- Solución: agregar la variable y hacer Redeploy

### Render se duerme entre requests (free tier)

Comportamiento esperado en el plan gratuito. El primer request tras 15 min de inactividad tarda ~30s. Para un demo esto es aceptable. Para producción real: Starter plan ($7/mes) en Render.

---

## 9. Tareas automáticas vs manuales

### ✅ Automático — ya está en el repo, no tocar

| Qué | Dónde |
|-----|-------|
| Build del frontend | `vercel.json` → `buildCommand` |
| SPA routing (rewrites) | `vercel.json` → `rewrites` |
| Cache de assets estáticos | `vercel.json` → `headers` |
| Migraciones al iniciar | `start.sh` → `alembic upgrade head` |
| Start command del backend | `render.yaml` → `startCommand: python -m alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` |
| Health check path | `render.yaml` → `healthCheckPath: /health` |
| CORS para `*.vercel.app` | `app/main.py` → `allow_origin_regex` |
| PostgreSQL connection pool | `app/database.py` → `pool_size=5, max_overflow=10` |
| Python version para Render | `runtime.txt` → `python-3.11.9` |

### 🖐️ Manual — tenés que hacer vos

| Qué | Dónde |
|-----|-------|
| Crear cuenta Supabase | supabase.com |
| Crear proyecto Supabase | Dashboard Supabase |
| Copiar `DATABASE_URL` | Supabase → Project Settings → Database |
| Crear servicio en Render | render.com → New → Web Service |
| Pegar env vars en Render | Render → Environment |
| Crear proyecto en Vercel | vercel.com → Add New Project |
| Pegar `VITE_API_URL` en Vercel | Vercel → Settings → Environment Variables |
| Redeploy en Vercel tras agregar vars | Vercel → Deployments → Redeploy |
| Crear App Password de Gmail | Google Account → Security → App Passwords |
| Crear primer usuario admin | Login con el usuario ya existente en SQLite (si migrás datos) o crear uno nuevo vía `/api/auth/register` |

---

## Notas adicionales

### ¿Migrar datos de SQLite a Supabase?

El deploy en Render arranca con una DB **vacía** (Alembic crea las tablas pero no carga datos). Si querés migrar los datos del `dev-local.db`:

```bash
# Exportar SQLite a SQL (en Windows: usar DB Browser for SQLite o sqlite3)
sqlite3 dev-local.db .dump > dump.sql

# Limpiar el dump: eliminar las líneas CREATE TABLE (ya las crea Alembic)
# y las líneas PRAGMA / sqlite-specific

# Importar en Supabase: Project → SQL Editor → pegar el INSERT INTO ...
```

O simplemente empezar con la DB vacía y registrar el primer usuario/hotel desde cero.

### Generar un Fernet key para INTEGRATIONS_ENCRYPTION_KEY

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Agregar esta variable en Render si querés cifrar integraciones (MercadoPago, PayPal, Gmail OAuth). Si no la seteás, usa el default del repo (no seguro para producción real).

### Generar JWT_SECRET manualmente (si no usás generateValue de Render)

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
