# Smoke QA

Suite mínima contra `app.main.app` con BD SQLite efímera.

## Comando único
```powershell
.\.venv\Scripts\python.exe tests\smoke\run_smoke.py
```

## Cobertura
- Estado inicial vacío (`/health`, `/api/onboarding/status`).
- Onboarding completo: owner, categorías, rooms, staff, finish.
- Aislamiento multihotel: owner/stado independiente por `X-Hotel-Id`.
- Permisos/headers: `X-Hotel-Id` + `X-User-Id` en `/api/config`.
- Connections `connect`: valida que responda 200; si falla queda xfail documentado.

## Artefactos
- `.pytest_cache/smoke/last_run.txt`
- `.pytest_cache/smoke/junit.xml`
