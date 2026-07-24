---
name: validate-all
description: Run the full local validation gate for Hotel Chipre PMS before pushing or merging — backend tests, frontend lint, typecheck and build, plus a migration dry-run. Use before any push/merge to main, or when the user asks to "validar", "check everything", or "correr todo".
---

# validate-all — puerta de validación pre-push

Corré esto **en este orden** y no declares "verde" sin ver el resultado de cada comando.
Este proyecto usa un entorno Python >=3.10 y Node 20 fuera del PATH por defecto.
No confíes en el nombre del directorio: el `.venv` histórico puede contener
Python 3.9 y debe rechazarse antes de importar la aplicación.

## 1. Backend — tests
```sh
cd "$(git rev-parse --show-toplevel)"
PYTHON_BIN="${E2E_PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
  for candidate in .venv/bin/python .venv312/bin/python python3.12 python3; do
    if [ -x "$candidate" ] && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi
if [ -z "$PYTHON_BIN" ]; then
  echo "Python >=3.10 is required; set E2E_PYTHON to the clean interpreter." >&2
  exit 1
fi
"$PYTHON_BIN" -m pytest -q
```
Esperado: 0 failed. Si algo falla, diagnosticá antes de seguir.

## 2. Frontend — lint + typecheck + build
```sh
export PATH="$HOME/.local/node/bin:$PATH"
cd "$(git rev-parse --show-toplevel)/frontend"
npm run lint          # eslint --max-warnings=0
npx tsc --noEmit      # typecheck
npm run build         # vite build
```
Los tres deben pasar sin errores (el warning de chunk >500 kB es deuda conocida, no bloquea).

## 3. Migraciones — dry-run sobre SQLite virgen (nunca la DB de dev)
```sh
cd "$(git rev-parse --show-toplevel)"
MIGRATION_PYTHON="${E2E_PYTHON:-${PYTHON_BIN:-}}"
if [ -z "$MIGRATION_PYTHON" ]; then
  for candidate in .venv/bin/python .venv312/bin/python python3.12 python3; do
    if [ -x "$candidate" ] && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      MIGRATION_PYTHON="$candidate"
      break
    fi
  done
fi
if [ -z "$MIGRATION_PYTHON" ]; then
  echo "Python >=3.10 is required for migrations." >&2
  exit 1
fi
DATABASE_URL="sqlite:///$(mktemp -d)/mig.db" "$MIGRATION_PYTHON" -m alembic upgrade head
```
Debe llegar a `head` sin error.

## Resultado
Reportá una tabla con el resultado de cada paso. Solo está "todo verde" si los tres pasan.
Recién ahí es seguro `git push` / mergear (ver preferencia: mergear a main sin esperar aprobación,
pero nunca algo roto a sabiendas).
