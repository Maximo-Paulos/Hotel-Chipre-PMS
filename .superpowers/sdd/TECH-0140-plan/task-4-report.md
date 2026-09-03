# TECH-0140 — Task 4 report

## Resultado

El outbox pasó a una forma v2 compatible con despliegue expand/backfill:
UUID de evento, versión, cursor durable opcional durante la transición,
deduplicación, estado de entrega, próximos reintentos y dead-letter.

## Cambios

- `app/models/domain_event_outbox.py`: campos v2, índices de recuperación y
  reintento, estados y restricciones de contadores.
- `app/models/domain_event_retention_watermark.py`: watermark tenant-scoped.
- `app/services/domain_events.py`: nuevos IDs/dedupe, recovery con
  `coalesce(stream_cursor, id)`, estados, máximo de 8 intentos y backoff
  acotado de 5 segundos a 15 minutos.
- `app/tasks/domain_event_tasks.py`: conserva replay por hotel y
  `SKIP LOCKED` PostgreSQL ya existente.
- `alembic/versions/tech0140_domain_event_outbox_v2.py`: migración aditiva,
  backfill determinístico de legacy, índices únicos y tabla de watermarks con
  RLS PostgreSQL.

## Semántica

La publicación continúa siendo at-least-once y nunca forma parte de la
respuesta de la mutación. Un fallo de Redis conserva la fila en PostgreSQL;
tras ocho intentos queda `dead_letter` y no se reintenta automáticamente.
Los errores persistidos sólo contienen tipo/código acotado.

## Validación

`18 passed` en outbox, recovery y migración existente; `git diff --check`
correcto. Los tests usan SQLite y doubles; no se ejecutó migración contra una
base provider-bound.

## Pendientes

La secuencia PostgreSQL definitiva y la fase enforce (`NOT NULL`/checks en una
segunda migración) requieren backfill medido y staging autorizado. El cleanup
por watermark, retención de siete días y resolución explícita de dead-letter
quedan para el job operativo de T8/T10.

## Rollback

Volver al código compatible anterior dejando las columnas aditivas. No se
ejecutan downgrades destructivos ni se eliminan filas.
