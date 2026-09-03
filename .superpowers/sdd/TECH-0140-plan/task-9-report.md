# Task 9 report — Seguridad, health y observabilidad

## Implementado

- `/health/live` sólo prueba que el proceso responde.
- `/health/ready` devuelve 503 si PostgreSQL no está disponible o si el mecanismo de lock requerido está deshabilitado; Redis caído se expone como degradado y se declara el fallback advisory PostgreSQL.
- `/health/datastores` conserva su contrato y usa el cliente Redis centralizado con timeouts comunes.
- Se agregó el puerto `Telemetry` y middleware HTTP con duración, route/path acotado, método, status y `X-Request-Id`, sin payloads ni parámetros SQL.

## Verificación

```text
13 passed, 22 warnings
```

Incluye healthchecks, fallback de lock, headers de seguridad, identidad de build y guardrail de rutas públicas.

## Pendiente provider-bound

- Integrar métricas/alertas del proveedor para pool, Redis, SSE, outbox, workers y almacenamiento.
- Reemplazar el log de timing por el exporter elegido cuando exista una decisión de observabilidad, conservando el puerto neutral.
