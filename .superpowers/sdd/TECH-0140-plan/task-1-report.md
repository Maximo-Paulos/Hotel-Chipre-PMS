# TECH-0140 — Task 1 report

## Resultado

Se endureció el flujo de Google sin modificar Apple ni realizar operaciones
OAuth externas. El login por subject conocido continúa funcionando; una cuenta
local encontrada por email ya no es vinculada automáticamente.

## Cambios

- `app/api/auth.py`: validación explícita de issuer, audience, expiración,
  subject, email verificado y dominios; alta Google controlada por
  `GOOGLE_SELF_SIGNUP_ENABLED`; respuesta `409 google_link_required`; endpoint
  autenticado `POST /api/auth/google/link`; endpoint público de capacidades.
- `app/schemas/auth.py`: contratos de link y capacidades públicas.
- `app/config.py` y `.env.example`: flags de self-signup y dominios permitidos.
- `frontend/src/api/auth.ts` y `frontend/src/api/client.ts`: clientes para
  capacidades y vinculación, manteniendo el flujo GIS existente.
- `tests/test_auth_security.py`: claims realistas y cobertura de alta apagada,
  link seguro/inseguro, capabilities y issuer/audience/expiración.

## Seguridad y límites

En producción el alta Google requiere `GOOGLE_SELF_SIGNUP_ENABLED=true` de
forma explícita. `GOOGLE_ALLOWED_DOMAINS` exige que el dominio del email y el
claim `hd` pertenezcan a la lista. No se guardan tokens ni claims en logs. El
endpoint de capacidades no devuelve secretos.

## Validación

- `.venv/bin/python -m pytest -q tests/test_auth_security.py`: `43 passed`,
  23 warnings preexistentes/no bloqueantes.
- `git diff --check`: correcto.
- `frontend/npm run typecheck`: no ejecutable porque este checkout no tiene
  `frontend/node_modules`/`tsc`; queda pendiente ejecutar después de `npm ci`.

## Pendientes y rollback

La prueba con Google real, configuración OAuth por ambiente y QA provider-bound
quedan `needs-verification`. El rollback de código es reversible: desactivar
Google o volver al commit anterior sin eliminar datos ni vínculos ya creados.
