# TECH-0140 — Task 0 report

## Resultado

Task 0 actualizó la baseline y la trazabilidad documental sin cambiar el
comportamiento de la aplicación ni provisionar/mutar proveedores externos.
El alcance quedó limitado al worktree
`/Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS-tech-0140`.

## Identidad del baseline

| Campo | Valor | Certeza |
| --- | --- | --- |
| Branch | `feature/tech-0140-realtime-recovery-contract` | `confirmed` |
| `code_sha` | `0fc3f497841b8da166631d5ca5d476943ed1dbd5` | `confirmed` |
| Estado inicial del árbol | limpio antes de editar | `confirmed` |
| Alembic head | `20260902_ota_lifecycle_enum_lowercase (head)` | `confirmed` |
| Estado final del árbol | cambios sólo de Task 0, antes del commit | `confirmed` |
| Ambiente | checkout local; sin validación cloud | `confirmed` / `needs-verification` |

El SHA corresponde al commit que ya contenía Task 2. La migración
`20260901_domain_event_outbox` crea el outbox durable; la revisión vigente
observada por Alembic es posterior y única.

## Cambios realizados

- `docs/HOTEL_PMS_MASTER_DEVELOPMENT_SPEC.md`: fecha de actualización y
  sección de baseline TECH-0140 con estado, SHA, branch, head, contrato de
  recovery, autoridad PostgreSQL y límites de proveedor.
- `docs/data-foundations/architecture-hybrid.md`: contrato de recuperación,
  papel del outbox, cursor `id`, límite de 500 filas, aislamiento tenant y
  separación PostgreSQL/Redis-Valkey.
- `docs/DEPLOY_GUIDE.md`: baseline operativa y configuración no sensible
  (`REALTIME_EVENTS_ENABLED=true`,
  `REALTIME_EVENTS_HEARTBEAT_SECONDS=15`, locks y bandera de callbacks).
- `scripts/knowledge/generate_inventories.py`: los artefactos pasan de SHA
  corto a SHA completo.
- `knowledge/_generated/`: inventarios regenerados desde el runtime/código
  vigente, incluyendo OpenAPI, rutas frontend, head Alembic, superficies cloud,
  resumen Graphify y README.

No se modificó `.graphify/` en este worktree. No se copiaron ni importaron los
seis cambios `.graphify` del checkout original
`/Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS`.

## Hechos verificados

1. `GET /api/events/recovery?after_cursor=N` está implementado en
   `app/api/events.py` y devuelve `latest_cursor`, `domains`,
   `reset_required` y `has_more`, sin payload de negocio.
2. El recovery resuelve el `hotel_id` desde la membresía autenticada y usa el
   outbox; `after_cursor=0`, cursor ausente, cursor anterior a la retención o
   más de 500 filas posteriores requieren refetch completo.
3. PostgreSQL conserva la autoridad transaccional. Redis/Valkey es transporte
   de realtime/estado efímero y no revierte una escritura confirmada.
4. La migración aplicada en el grafo de Alembic tiene un único head:
   `20260902_ota_lifecycle_enum_lowercase`.
5. Los inventarios regenerados contienen el SHA completo
   `0fc3f497841b8da166631d5ca5d476943ed1dbd5` y reflejan 365 paths/432
   operaciones OpenAPI en este checkout.

## Inferencias y pendientes

- `inferred`: la respuesta metadata-only permite evolucionar el cursor a
  `stream_cursor` en T4 sin exponer datos de negocio, siempre que se mantenga
  el contrato público documentado.
- `needs-verification`: salud y disponibilidad de Redis/Valkey del proveedor,
  retención bajo carga productiva, QA entre dispositivos, URLs privadas,
  variables privadas y cualquier evidencia cloud.
- `needs-verification`: no se ejecutó PostgreSQL/Supabase remoto ni una
  migración remota; el head informado es la salida local de Alembic.

## Validación ejecutada

| Comando | Resultado |
| --- | --- |
| `.venv/bin/python -m pytest -q tests/test_realtime_recovery.py` | `7 passed`, 22 warnings no bloqueantes |
| `.venv/bin/python -m compileall -q scripts/knowledge/generate_inventories.py` | exit 0 |
| `.venv/bin/python scripts/knowledge/generate_inventories.py` | exit 0 |
| `.venv/bin/python -m alembic heads` | un único head: `20260902_ota_lifecycle_enum_lowercase (head)` |
| `git diff --check` | exit 0 |

Las advertencias de pytest son de dependencias/deprecaciones y warnings ORM
preexistentes durante el test; no produjeron fallos.

## Riesgos y rollback

El riesgo restante es confundir esta baseline local con una certificación de
proveedor o QA cloud. La mitigación queda explícita como
`needs-verification`; ninguna URL, credencial o secreto se afirma como
confirmado. El rollback es documental: revertir el commit de Task 0 y
regenerar los inventarios desde el checkout correspondiente. No hay migración,
deploy ni operación externa asociada a Task 0.
