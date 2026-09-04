# TECH-0140 — Task 5 report

## Resultado

SSE y el cliente web ahora transportan identificadores/cursor de stream y
recuperan invalidaciones confirmadas desde PostgreSQL antes de abrir o reabrir
la conexión. Si Redis/Valkey no responde, el endpoint mantiene SSE leyendo el
outbox confirmado de PostgreSQL con sesiones cortas. El cliente deduplica
eventos, ignora cursores viejos y dispone de polling degradado visible/oculto.

## Cambios

- `app/services/domain_events.py`: envelope con `event_id`, `schema_version`,
  `cursor`; `id:` SSE; límite de 4 KiB; fallback SSE desde outbox PostgreSQL
  sin payload de negocio.
- `frontend/src/sync/crossTabSync.ts`: cursor por usuario/hotel en
  `sessionStorage`, recovery acotado, cursor enviado al abrir SSE, dedupe y
  polling 15/60 segundos cuando SSE no está conectado.
- `tests/test_domain_events.py`: contrato actualizado para envelope v2.

## Seguridad

El stream continúa hotel-scoped y sólo transporta invalidaciones; el frontend
refetchea APIs autorizadas. El recovery nunca devuelve payload. No se agregan
tokens, PII ni bytes de negocio al evento.

## Validación

`26 passed` en eventos y recovery; `19 passed` en datastores y seguridad;
lint, typecheck, build y pruebas auxiliares frontend correctos; `git diff
--check` correcto.

## Pendientes

La revalidación de membresía cada 60 segundos durante una conexión larga y la
prueba E2E multi-sesión requieren staging autorizado. El fallback mantiene la
corrección funcional ante Redis caído, pero su latencia/capacidad en proveedor
y la coedición WebSocket siguen requiriendo validación provider-bound.

## Rollback

Desactivar el cliente v2 y volver al refetch actual; las columnas del outbox
son aditivas y no requieren downgrade.
