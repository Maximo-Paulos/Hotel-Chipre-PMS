# Task 6 report — PostgreSQL, consultas y concurrencia

## Implementado

- Se agregaron parámetros explícitos para pool, conexión, recycle y `statement_timeout`.
- El engine PostgreSQL aplica `pool_timeout`, `connect_timeout`, `pool_recycle` y un `statement_timeout` por conexión.
- El pool queda acotado a `5 + 2` por proceso como baseline local; el cálculo de instancias y capacidad del proveedor sigue siendo provider-bound.
- `render.yaml`, `.env.example` y la documentación de arquitectura reflejan el presupuesto conservador y no afirman capacidad no medida.
- En producción, habilitar Google Login exige declarar explícitamente la política de self-signup.

## Verificación

```text
48 passed, 22 warnings
```

Comando focal:

```bash
.venv/bin/python -m pytest -q \
  tests/test_runtime_security.py \
  tests/test_database_schema_bootstrap.py \
  tests/test_domain_events.py \
  tests/test_domain_event_outbox.py \
  tests/test_realtime_recovery.py
```

Los warnings SQLAlchemy de relaciones con claves foráneas parcialmente superpuestas quedan registrados para la auditoría de concurrencia/ORM; no se silencian especulativamente.

## Pendiente provider-bound

- Confirmar `max_connections`, plan, PgBouncer/PITR y presupuesto real antes de usar autoscaling.
- Ejecutar `EXPLAIN (ANALYZE, BUFFERS)` con consultas representativas antes de crear índices adicionales.
