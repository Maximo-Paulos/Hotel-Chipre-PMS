# TECH-0140 — Task 3 report

## Resultado

Se agregó una frontera interna para capacidades efímeras y una construcción
compartida de clientes Redis/Valkey. PostgreSQL sigue siendo la autoridad y
los consumidores mantienen sus fallbacks existentes.

## Cambios

- `app/adapters/ephemeral.py`: puertos `CacheStore`, `EventBus` y
  `LockManager`.
- `app/infrastructure/redis_backend.py`: cliente sync/async cacheado por
  proceso, timeouts acotados, namespace configurable y reset para shutdown o
  tests.
- `app/config.py` y `.env.example`: `REDIS_NAMESPACE` y timeouts de conexión y
  socket.
- `app/services/domain_events.py`: cliente compartido para realtime y
  namespace aplicado a canales y claves de revisión.
- `app/services/distributed_lock.py`: cliente compartido y namespace aplicado
  a leases.
- `tests/test_ephemeral_backend.py`: aislamiento de namespace y reutilización
  del cliente.

## Validación

`38 passed` en los tests focales de puertos, locks, eventos, cache y health;
`git diff --check` correcto. Los tests existentes conservan doubles con claves
legacy porque el namespace queda vacío por defecto para compatibilidad local.

## Pendientes

La migración de collaboration, read-model cache y health a todos los puertos
queda para una iteración posterior: se conserva su comportamiento probado y
el nuevo backend ya está disponible para el siguiente corte. En ambientes
compartidos se debe configurar `REDIS_NAMESPACE` explícitamente. Redis/Valkey
real, TLS/ACL y métricas provider-bound quedan `needs-verification`.

## Rollback

Revertir el commit y quitar las variables nuevas; no hay migración ni mutación
externa.
