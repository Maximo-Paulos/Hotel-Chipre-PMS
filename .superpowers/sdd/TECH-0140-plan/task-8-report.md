# Task 8 report — Jobs, workers y backpressure

## Implementado

- `JobDispatcher` define un puerto portable y `CeleryJobDispatcher` mantiene Celery como implementación inicial.
- `TASK_SPECS` separa colas `critical` y `heavy` con límites de tiempo y retries explícitos.
- `dispatch_once` registra una intención tenant-scoped con `(hotel_id, task_name, deduplication_key)` único y propaga `hotel_id`, `correlation_id` y dedupe en headers.
- Se agregaron `job_dispatch_records` y `service_heartbeats` con migración Alembic y RLS para los registros tenant-scoped.
- El replay del outbox emite heartbeat durable; el scheduler continúa siendo un único beat con lease/idempotencia existente.

## Verificación

```text
12 passed, 22 warnings
```

Incluye dispatcher/dedupe, heartbeat, schedule de analytics y salud de datastores. No se levantó un worker contra un broker remoto.

## Pendiente provider-bound

- Verificar workers/beat activos, oldest-age/lag y throughput en un staging aislado.
- Ajustar concurrencia y límites al presupuesto real de PostgreSQL; las colas pueden seguir siendo atendidas por un único worker inicialmente.
