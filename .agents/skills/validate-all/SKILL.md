---
name: validate-all
description: Run the full local validation gate for Hotel Chipre PMS before pushing or merging — PostgreSQL-only backend tests and migration validation, frontend lint, typecheck, tests and build. Use before any push/merge to main, or when the user asks to "validar", "check everything", or "correr todo".
---

# validate-all — puerta de validación pre-push

Corré esto **en este orden** y no declares "verde" sin ver el resultado de cada comando.
Este proyecto usa un entorno Python >=3.10 y Node 20 fuera del PATH por defecto.
No confíes en el nombre del directorio: el `.venv` histórico puede contener
Python 3.9 y debe rechazarse antes de importar la aplicación.

Para cualquier validación con base, aplica también la skill global
`colima-postgres-only`. Crea una base PostgreSQL 16 nueva en Colima, usa un DSN
loopback explícito con la guarda de aislamiento de `tests/postgres_test_safety.py`
y efectos externos apagados. No cargues el DSN desde `.env`, no permitas fallback
a SQLite y no borres perfiles, volúmenes ni bases preexistentes.

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
Esperado: 0 failed. Antes de ejecutarlo, confirma que la selección completa no
creará bases SQLite: el `db_engine` heredado de `tests/conftest.py` y algunos
módulos antiguos todavía pueden abrir SQLite directamente. Si la suite no puede
quedar completamente PostgreSQL, porta esos fixtures primero; no cuentes una
selección parcial como suite completa ni informes “todo verde”.

## 2. Frontend — lint + typecheck + tests + build
```sh
export PATH="$HOME/.local/node/bin:$PATH"
cd "$(git rev-parse --show-toplevel)/frontend"
npm run lint          # eslint --max-warnings=0
npx tsc --noEmit      # typecheck
npm test              # node --test *.test.mjs (manifest PWA, i18n, CSV, marketing HTML, build meta)
npm run build         # vite build
```
Los cuatro deben pasar sin errores (el warning de chunk >500 kB es deuda conocida, no bloquea).
`npm test` estuvo fuera de esta puerta y de CI hasta 2026-09-17: el test del manifest PWA
quedó desactualizado meses sin que nadie lo viera. No lo saques de la lista.

## 3. Migraciones — instalación limpia sobre una base PostgreSQL virgen de Colima
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
APP_ENV=test DATABASE_URL="$POSTGRES_MIGRATION_TEST_URL" "$MIGRATION_PYTHON" -m alembic upgrade head
```
`POSTGRES_MIGRATION_TEST_URL` debe apuntar a una base PostgreSQL loopback nueva y
desechable, distinta de las bases persistentes. Valida antes el destino exacto;
debe llegar a `head` sin error. No sustituyas PostgreSQL por SQLite si Colima no
está disponible.

## Resultado
Reportá una tabla con el resultado de cada paso. Solo está "todo verde" si los tres pasan.
Recién ahí es seguro `git push` / mergear (ver preferencia: mergear a main sin esperar aprobación,
pero nunca algo roto a sabiendas).
