# Sincronización y coedición en tiempo real

## Alcance

El PMS conserva PostgreSQL como fuente de verdad. La sincronización en tiempo
real sólo transporta señales de invalidación: cada cliente vuelve a consultar
la API autenticada antes de presentar el estado confirmado.

La confirmación de una mutación y la actualización posterior de las vistas son
pasos separados:

1. el endpoint confirma la escritura y su respuesta confirma el guardado;
2. `refreshAfterMutation` marca stale las consultas afectadas del hotel e inicia
   los refetch activos en segundo plano, sin retener el éxito del guardado;
3. se conserva el último dato correcto hasta que llegue la respuesta nueva; las
   consultas inactivas se reconcilian al volver a abrir su vista.

La recuperación por SSE/recovery también usa `refreshDomains` para volver a
consultar el estado autoritativo. La respuesta de lectura reconcilia la vista;
no determina si la escritura se confirmó.

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
fallback durante un despliegue mixto. La API marca `reset_required=true` si no
se envió cursor, `after_cursor=0`, el cursor antecede a las filas retenidas o
hay más de 500 filas posteriores. El barrido devuelve como máximo 500 filas y
`has_more` informa que alcanzó ese límite.

El primer recovery con cursor ausente/0 es una carga normal, aunque el backend
marque `reset_required=true` para señalar que no hubo cursor previo. Después de
las consultas iniciales, el cliente hace una única reconciliación de los
dominios devueltos por recovery y sólo para consultas activas del hotel; así
cierra la carrera entre esas lecturas y `latest_cursor` sin volver a cargar
consultas inactivas. Si `has_more=true`, la lista pudo quedar truncada y se
reconcilian todos los dominios conocidos, todavía sólo en consultas activas.
Luego guarda `latest_cursor` y abre el stream desde allí. Un cursor conocido con
`reset_required=true` también reconcilia todos los dominios del hotel; una
recuperación normal invalida sólo los dominios devueltos. En todos los casos,
las consultas inactivas no generan requests de red y se actualizan cuando una
vista las monta de nuevo.

El recolector de `app.services.domain_events` guarda las señales en la sesión,
elimina duplicados y las publica desde `after_commit`. `after_rollback`
descarta las señales. El outbox de PostgreSQL es durable. Si
`POSTGRES_EVENT_LISTENER_ENABLED=true` y el API puede abrir una conexión de
sesión PostgreSQL, un trigger envía por `NOTIFY` sólo metadatos de invalidación
y un listener por proceso los distribuye a los streams activos. En el pooler de
transacciones de Supabase (puerto 6543), `LISTEN` no mantiene una sesión y se
usa el fallback SQL acotado: un sondeo cada 60 segundos por hotel activo y
proceso, compartido entre sus streams. Si el listener se desconecta, el hub
vuelve a ese fallback y recupera el cursor desde el outbox. Redis/Valkey queda
opcional para el SSE. La coedición puede usar `COLLABORATION_BACKEND=process`
con tickets y fan-out acotados a una sola instancia; Redis/Valkey se necesita
para distribuir borradores entre varios procesos. Los procesos Celery que usan
ese broker también necesitan Redis. Los fallos del transporte no deshacen una
operación ya guardada.

Si `DATABASE_URL` usa el pooler de transacciones, configure opcionalmente
`POSTGRES_EVENT_LISTENER_DATABASE_URL` con una URL Supabase de sesión o directa
por el puerto 5432. El listener abre una sola conexión adicional por proceso
mientras haya streams; la API sigue usando `DATABASE_URL` para las consultas
normales. No registre ninguna de esas URLs.

El cliente combina SSE con `BroadcastChannel` y el fallback de `localStorage`
para pestañas del mismo navegador. Las mutaciones del navegador incluyen un
UUID opaco de correlación en su evento de dominio; la pestaña que inició la
escritura omite sólo la repetición del mismo UUID y dominio, mientras las otras
pestañas siguen reconciliando su estado. Ese UUID no cambia autenticación ni
autorización. El cliente persiste el cursor por usuario/hotel, deduplica
`event_id`, agrupa eventos cercanos en una invalidación por dominio,
ejecuta recovery antes de abrir o reabrir SSE y repara gaps sin retroceder
cursores. SSE reconecta con backoff exponencial y jitter.
Si nunca conecta o queda degradado, hace recovery cada 5 segundos en pestañas
visibles y aplica backoff hasta 30 segundos ante fallos. Las pestañas ocultas
pausan ese polling y se recuperan al volver a primer plano. El shell conserva
los datos visibles y muestra que pueden estar desactualizados. El backend revalida la
membresía cada 60 segundos; al revocarse envía una señal de control, cierra el
stream y obliga a reautenticarse.

Configuración relevante:

```dotenv
REDIS_URL=redis://localhost:6379/0
REALTIME_EVENTS_ENABLED=true
REALTIME_EVENTS_HEARTBEAT_SECONDS=15
REALTIME_EVENTS_FALLBACK_POLL_SECONDS=5
DISTRIBUTED_LOCK_ENABLED=true
DISTRIBUTED_LOCK_REQUIRED=true   # producción
```

Para tests E2E locales, Playwright puede desactivar explícitamente el cliente
realtime. El camino PostgreSQL requiere aplicar la migración del trigger
`LISTEN/NOTIFY` y comprobar que la URL del listener usa una conexión directa o
de sesión; con el pooler de transacciones seguirá activo el fallback de 60
segundos. Redis/Valkey no es requisito para el SSE ni para los locks que usan
el fallback de advisory locks PostgreSQL. Con `COLLABORATION_BACKEND=process`,
la coedición WebSocket guarda tickets y mantiene presencia/borradores sólo en
memoria del proceso; por eso exige una instancia y un worker de API. Antes de
escalar a varios procesos o instancias hay que cambiar a Redis/Valkey y probar
el fan-out. Los servicios Celery que usan Redis también lo requieren.

## Coedición por campo

La coedición es una capa de borradores y presencia, no un CRDT de texto. El
flujo autenticado es:

- `POST /api/collaboration/tickets`: emite un ticket corto, vinculado al hotel,
  usuario, recurso, permisos y campos permitidos; se guarda en Redis o en un
  almacén acotado en memoria, según `COLLABORATION_BACKEND`, y sólo puede
  consumirse una vez.
- `WS /api/collaboration/ws`: consume el ticket y transmite presencia y
  `draft_patch` efímeros. Redis pub/sub permite fan-out entre workers; el
  backend `process` lo mantiene dentro de una sola instancia.
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
