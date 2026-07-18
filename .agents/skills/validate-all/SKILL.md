---
name: validate-all
description: Run the full local validation gate for Hotel Chipre PMS before pushing or merging — backend tests, frontend lint, typecheck and build, plus a migration dry-run. Use before any push/merge to main, or when the user asks to "validar", "check everything", or "correr todo".
---

# validate-all — puerta de validación pre-push

Corré esto **en este orden** y no declares "verde" sin ver el resultado de cada comando.
Este proyecto usa un venv propio (Python 3.12) y Node 20 fuera del PATH por defecto.

## 1. Backend — tests
```sh
cd /Users/maximopaulos/Desktop/Hotel-Chipre-PMS
.venv/bin/python -m pytest -q
```
Esperado: `~749 passed` (0 failed). Si algo falla, diagnosticá antes de seguir.

## 2. Frontend — lint + typecheck + build
```sh
export PATH="$HOME/.local/node/bin:$PATH"
cd /Users/maximopaulos/Desktop/Hotel-Chipre-PMS/frontend
npm run lint          # eslint --max-warnings=0
npx tsc --noEmit      # typecheck
npm run build         # vite build
```
Los tres deben pasar sin errores (el warning de chunk >500 kB es deuda conocida, no bloquea).

## 3. Migraciones — dry-run sobre SQLite virgen (nunca la DB de dev)
```sh
cd /Users/maximopaulos/Desktop/Hotel-Chipre-PMS
DATABASE_URL="sqlite:///$(mktemp -d)/mig.db" .venv/bin/python -m alembic upgrade head
```
Debe llegar a `head` sin error.

## Resultado
Reportá una tabla con el resultado de cada paso. Solo está "todo verde" si los tres pasan.
Recién ahí es seguro `git push` / mergear (ver preferencia: mergear a main sin esperar aprobación,
pero nunca algo roto a sabiendas).
