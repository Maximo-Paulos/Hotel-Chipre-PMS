# Hotel Chipre PMS - Stage 1 Usage

## Quick Start (local trial)
- Prereqs: Python 3.11+, Node 20+, npm, HTTPie (`pip install httpie`) or Postman.
- 1. `python -m venv .venv`
- 2. `.\\.venv\\Scripts\\activate`
- 3. `pip install -r requirements.txt`
- 4. `cd frontend && npm install`
- 5. Build UI: `npm run build` (served from `frontend/dist`). If `spawn EPERM` aparece en OneDrive, corré el build en WSL/fuera de OneDrive o permití `esbuild.exe`.
- 6. Volvé al root y levantá todo con `npx nodemon` (lee `nodemon.json` -> uvicorn con reload). UI + API en `http://127.0.0.1:8000`. Dev UI sigue en `npm run dev`.

### Base de datos (arranca vacía)
- Migraciones: `alembic upgrade head` (usa `DATABASE_URL` de `.env`).
- (Opcional) Seed demo manual: `python -m app.scripts.seed_demo` — solo si querés datos de ejemplo.

### Gemma local (mock rapido)
- Para probar la integracion de Gemma sin modelo real:
```bash
python -m app.scripts.mock_gemma_runtime --port 11434
```
- Variables recomendadas:
  - `GEMMA_ENABLED=true`
  - `GEMMA_PROVIDER=openai_compatible`
  - `GEMMA_ENDPOINT_URL=http://127.0.0.1:11434/v1/chat/completions`
  - `GEMMA_MODEL=gemma-mock-local`
- Diagnostico: `GET /api/gemma/chat/runtime-status`

## Deploy (Docker / Compose)
1) Build imagenes  
```bash
docker compose build
```
- El frontend corre `npm run build` dentro de la imagen y se sirve con Nginx (puerto 8080).  
- El backend usa `uvicorn` y expone 8000.

2) Levantar stack  
```bash
docker compose up -d
```
Servicios: frontend http://localhost:8080, backend http://localhost:8000, Postgres con credenciales `pms/pms` (puerto 5432, DB `hotel_pms`).

3) Migraciones Alembic  
```bash
docker compose run --rm backend alembic upgrade head
```
Toma `DATABASE_URL` del compose. Para SQLite local: `DATABASE_URL=sqlite:///./dev.db alembic upgrade head`.

4) Seed/reset demo (opcional, solo si `DEMO_MODE=true`)  
   - Poblar datos demo: `curl -X POST http://localhost:8000/api/seed`
   - Reset vacío (sin seed): `curl -X POST http://localhost:8000/api/reset`

## Headers
- Add `X-Hotel-Id` on every mutating call (defaults to the first persisted hotel if omitted).

## Auth & Email
- Registro/Login/Verificación/Reset: `/api/auth/*` (envía emails si `SMTP_*` está configurado; si `DEMO_MODE=true` devuelve el código en la respuesta).
- JWT: header `Authorization: Bearer <token>`. Claves en `.env`: `JWT_SECRET`, `JWT_EXPIRES_MINUTES`, `JWT_ALGORITHM`.
- Rate limit de login (in-memory): `LOGIN_RATE_LIMIT` intentos por ventana de 15 min.
- SMTP env vars: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_STARTUP_NOTIFY` (default False, así no spamea al iniciar).
- Add `X-User-Id` for auditing; values are free-form.

## Key Stage 1 Endpoints
| Method & Path | Purpose |
| --- | --- |
| GET `/health` | Liveness probe. |
| GET `/api/onboarding/status` | Check pending onboarding steps and counts. |
| POST `/api/onboarding/owner` | Store owner contact (name, email, phone, role). |
| POST `/api/onboarding/categories` | Upsert room categories. |
| POST `/api/onboarding/rooms` | Upsert rooms by number, floor, `category_code`. |
| POST `/api/onboarding/staff` | Store staff roster. |
| POST `/api/onboarding/finish` | Mark onboarding complete. |
| GET `/api/rooms/categories` | List category ids/codes for later calls. |
| GET `/api/rooms/availability` | Quick availability by `category_id`, `check_in_date`, `check_out_date`. |
| POST `/api/guests` | Create guest with optional companions. |
| POST `/api/reservations` | Create reservation (guest + category, optional room). |
| POST `/api/payments` | Record deposit/full/partial payments. |
| POST `/api/checkin/{reservation_id}` | Transition to checked-in. |
| POST `/api/checkin/checkout/{reservation_id}` | Transition to checked-out. |

## HTTPie happy path
```powershell
$env:BASE="http://127.0.0.1:8000"
$env:HOTEL=1
$env:USER="owner-1"

# Health & status
http GET $env:BASE/health
http GET $env:BASE/api/onboarding/status X-Hotel-Id:$env:HOTEL X-User-Id:$env:USER

# Onboarding steps
http POST $env:BASE/api/onboarding/owner X-Hotel-Id:$env:HOTEL X-User-Id:$env:USER name="Ana Owner" email="ana@chipre.test" phone="+54 11 5555 1234" role="Owner"
http POST $env:BASE/api/onboarding/categories X-Hotel-Id:$env:HOTEL X-User-Id:$env:USER categories:='[{"name":"Doble","code":"DBL","base_price_per_night":45,"max_occupancy":2},{"name":"Triple","code":"TPL","base_price_per_night":70,"max_occupancy":3}]'
http POST $env:BASE/api/onboarding/rooms X-Hotel-Id:$env:HOTEL X-User-Id:$env:USER rooms:='[{"room_number":"101","floor":1,"category_code":"DBL"},{"room_number":"102","floor":1,"category_code":"TPL"}]'
http POST $env:BASE/api/onboarding/staff X-Hotel-Id:$env:HOTEL X-User-Id:$env:USER staff:='[{"name":"Recepcion","role":"Front Desk","email":"fd@chipre.test"}]'
http POST $env:BASE/api/onboarding/finish X-Hotel-Id:$env:HOTEL X-User-Id:$env:USER

# Book a stay
http POST $env:BASE/api/guests X-Hotel-Id:$env:HOTEL X-User-Id:$env:USER first_name="Juan" last_name="Perez" email="juan@test.com" phone="+54 9 11 4444 0000" terms_accepted:=true
http POST $env:BASE/api/reservations X-Hotel-Id:$env:HOTEL X-User-Id:$env:USER guest_id:=1 category_id:=1 check_in_date=2026-04-05 check_out_date=2026-04-07 num_adults:=2 source=direct
http POST $env:BASE/api/payments X-Hotel-Id:$env:HOTEL X-User-Id:$env:USER reservation_id:=1 amount:=30 payment_method=cash transaction_type=deposit currency=ARS description="Deposit for stay"
http POST $env:BASE/api/checkin/1 X-Hotel-Id:$env:HOTEL X-User-Id:$env:USER
http POST $env:BASE/api/checkin/checkout/1 X-Hotel-Id:$env:HOTEL X-User-Id:$env:USER
```

## Onboarding checklist (hotel trial)
- Owner contact captured and onboarding status shows `completed: true`.
- Room categories, room numbers, and floors entered match the physical inventory.
- Deposit percentage/accepted payment methods agreed (cash, transfer, Mercado Pago, PayPal, card, bank_transfer).
- Staff roster saved with at least one front-desk contact.
- Test guest + reservation created; payment recorded; balance due matches expectation.
- Check-in and checkout endpoints exercised once.

## Postman
- A ready collection lives at `docs/Stage1.postman_collection.json` with the same flow above. Import it and set `baseUrl`, `hotelId`, and `userId` variables.
