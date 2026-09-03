# Sincronización y coedición en tiempo real

## Alcance

El PMS conserva PostgreSQL como fuente de verdad. La sincronización en tiempo
real sólo transporta señales de invalidación: cada cliente vuelve a consultar
la API autenticada antes de presentar el estado confirmado.

La garantía de interfaz para una mutación es:

1. el endpoint confirma la escritura;
2. la mutación usa `mutateAsync`;
3. `refreshAfterMutation` invalida las consultas activas del hotel y espera su
   refetch;
4. recién después se muestra éxito, se cierra el modal o se habilita la
   siguiente operación crítica.

Las claves operativas deben incluir el `hotelId`. El registro centralizado vive
en `frontend/src/api/queryKeys.ts`; la invalidación tenant-safe vive en
`frontend/src/api/queryInvalidation.ts`. Las consultas inactivas quedan stale y
se reconcilian al abrirse.

## Eventos entre pestañas, procesos y dispositivos

El backend expone `GET /api/events/stream` como SSE. Las mutaciones publican un
evento por hotel y dominio después del `commit` de SQLAlchemy. El payload es
un aviso mínimo con identificadores operativos; nunca incluye importes,
comprobantes, credenciales, tokens ni PII innecesaria.

Si el navegador pierde una señal o se reconecta desde un cursor conocido,
puede llamar a `GET /api/events/recovery?after_cursor=N`. La respuesta sólo
contiene `latest_cursor`, los `domains` modificados, `reset_required` y
`has_more`; no devuelve payloads ni datos de negocio. La consulta está siempre
limitada al hotel resuelto por la membresía autenticada e incluye filas del
outbox pendientes y publicadas, porque ambas representan commits reales.

`latest_cursor` usa `stream_cursor` en outbox v2 y conserva el `id` entero como
fallback durante un despliegue mixto. La ausencia de cursor, `after_cursor=0`,
un cursor anterior a las filas retenidas o más de 500 filas posteriores
obligan a un refetch completo desde la API autoritativa
(`reset_required=true`). El barrido devuelve como máximo 500 filas y
`has_more` informa que el límite fue alcanzado.

El recolector de `app.services.domain_events` guarda las señales en la sesión,
elimina duplicados y las publica desde `after_commit`. `after_rollback`
descarta las señales. Redis/Valkey es el transporte requerido para que el
flujo funcione entre workers y dispositivos; los fallos del transporte no
deshacen una operación ya guardada.

El cliente combina SSE con `BroadcastChannel` y el fallback de `localStorage`
para pestañas del mismo navegador. Persiste el cursor por usuario/hotel,
deduplica `event_id`, ejecuta recovery antes de abrir o reabrir SSE y repara
gaps sin retroceder cursores. SSE reconecta con backoff exponencial y jitter.
Si nunca conecta o queda degradado, hace polling en primer plano cada 15
segundos y en segundo plano cada 60 segundos. El shell conserva los datos
visibles y muestra que pueden estar desactualizados. El backend revalida la
membresía cada 60 segundos; al revocarse envía una señal de control, cierra el
stream y obliga a reautenticarse.

Configuración relevante:

```dotenv
REDIS_URL=redis://localhost:6379/0
REALTIME_EVENTS_ENABLED=true
REALTIME_EVENTS_HEARTBEAT_SECONDS=15
DISTRIBUTED_LOCK_ENABLED=true
DISTRIBUTED_LOCK_REQUIRED=true   # producción
```

Para tests E2E locales sin Redis, Playwright desactiva explícitamente el
cliente realtime; para verificar el camino distribuido se puede ejecutar con
`REALTIME_E2E=true` y Redis/Valkey activo. En producción, Redis/Valkey debe estar disponible: la
validación de arranque exige `REALTIME_EVENTS_ENABLED=true` y los locks
distribuidos.

## Coedición por campo

La coedición es una capa de borradores y presencia, no un CRDT de texto. El
flujo autenticado es:

- `POST /api/collaboration/tickets`: emite un ticket corto, vinculado al hotel,
  usuario, recurso, permisos y campos permitidos; se guarda en Redis y sólo
  puede consumirse una vez.
- `WS /api/collaboration/ws`: consume el ticket y transmite presencia y
  `draft_patch` efímeros. Redis pub/sub permite fan-out entre workers.
- `PATCH /api/collaboration/resources/{resource_type}/{resource_id}`: persiste
  los cambios con `base_revision` y `base_values`, bajo autorización y
  tenant-scope del servidor.

Los campos editables están allowlisteados por tipo de recurso. Un cambio
remoto en un campo que el operador local no está editando se incorpora
automáticamente. Cambios sobre campos distintos se combinan. Si el mismo
campo cambió desde la revisión base, la API responde `409` con:
`code`, `server_revision`, `server_resource` y `conflicting_fields`; la UI
permite conservar el valor propio o aceptar el remoto.

Contraseñas, tokens, claves API, datos de sesión, comprobantes binarios,
firmas digitales y otros secretos no pertenecen al canal de borradores. Los
pagos, reembolsos, check-in, checkout y cancelaciones no son recursos
colaborativos: conservan sus endpoints atómicos, idempotencia y auditoría.

## Reportes

Las vistas transaccionales se refrescan con la confirmación de PostgreSQL.
Reportes y almacenes analíticos pueden mantener una latencia propia; deben
mostrar o conservar su `data_as_of` cuando el endpoint lo provea y no prometer
consistencia instantánea de un almacén eventual.

## Validación

La regresión principal está en
`frontend/e2e/reservation-drawer-global.spec.ts`: registrar un pago, cerrar y
reabrir el drawer sin recargar debe mostrar el estado confirmado. Los tests de
backend cubren deduplicación post-commit, descarte por rollback, aislamiento
tenant, tickets de un solo uso y conflictos estructurados.
