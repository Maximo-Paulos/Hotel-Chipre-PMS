# TECH-0140 — Task 5 report

## Resultado

SSE y el cliente web ahora transportan identificadores/cursor de stream y
recuperan invalidaciones confirmadas desde PostgreSQL antes de abrir o reabrir
la conexión. El cliente deduplica eventos, ignora cursores viejos y dispone de
polling degradado visible/oculto.

## Cambios

- `app/services/domain_events.py`: envelope con `event_id`, `schema_version`,
  `cursor`; `id:` SSE; límite de 4 KiB.
- `frontend/src/sync/crossTabSync.ts`: cursor por usuario/hotel en
  `sessionStorage`, recovery acotado, dedupe y polling 15/60 segundos cuando
  SSE no está conectado.
- `tests/test_domain_events.py`: contrato actualizado para envelope v2.

## Seguridad

El stream continúa hotel-scoped y sólo transporta invalidaciones; el frontend
refetchea APIs autorizadas. El recovery nunca devuelve payload. No se agregan
tokens, PII ni bytes de negocio al evento.

## Validación

`31 passed` en eventos, outbox y recovery; `git diff --check` correcto. El
typecheck Vitest/TypeScript queda pendiente porque `frontend/node_modules` no
está instalado en este worktree.

## Pendientes

La revalidación de membresía cada 60 segundos durante una conexión larga y la
prueba E2E multi-sesión requieren staging autorizado. El polling queda como
guardrail local y no es evidencia de p95 provider-bound.

## Rollback

Desactivar el cliente v2 y volver al refetch actual; las columnas del outbox
son aditivas y no requieren downgrade.
