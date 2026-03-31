# Hotel Chipre PMS - Stage 1 Usage

## Quick Start (local trial)
- Prereqs: Python 3.11+, Node 20+, npm, HTTPie (`pip install httpie`) or Postman.
- 1. `python -m venv .venv`
- 2. `.\\.venv\\Scripts\\activate`
- 3. `pip install -r requirements.txt`
- 4. `cd frontend && npm install`
- 5. Build UI: `npm run build` (served from `frontend/dist`). If `spawn EPERM` appears on this OneDrive host, run the build in WSL/outside OneDrive or allow `esbuild.exe` in AV/Controlled Folder Access.
- 6. Start API + UI shell from repo root: `npx nodemon` (uses `nodemon.json` -> uvicorn with reload). Set `DEMO_MODE=true` before running if you need `/api/seed` or `/api/reset`.
- 7. UI + API live at `http://127.0.0.1:8000`. Dev-only UI at `npm run dev` still works via Vite proxy to the backend on port 8000.

## Headers
- Add `X-Hotel-Id` on every mutating call (defaults to the first persisted hotel if omitted).
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
