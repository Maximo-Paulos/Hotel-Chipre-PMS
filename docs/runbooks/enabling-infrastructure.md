# Activar infraestructura opcional

Esta guía responde, en cada sección, qué se cambia y qué efecto tiene. El
servicio web free que está activo hoy fue creado manualmente fuera del
Blueprint; no se modificó ningún recurso cloud durante esta tarea.

## ¿Qué cambio para activar Redis y el cache de read-models?

En el proceso que atiende el API, cambie `READ_MODEL_CACHE_ENABLED` de `false` a
`true` y configure `REDIS_URL` con la URL del Redis/Valkey contratado. En el
Blueprint de Render, `REDIS_URL` se obtiene de
`hotel-chipre-pms-redis`; en otra plataforma debe apuntar al servicio Redis de
esa plataforma. El mismo endpoint puede usarse para
`CELERY_BROKER_URL` y `CELERY_RESULT_BACKEND` cuando también se habiliten
worker y beat.

Esto agrega el costo de una instancia Redis/Valkey paga; el importe exacto
depende del proveedor y plan vigente y no está verificado en este checkout.
Con el cache activo, las lecturas cacheables de disponibilidad de habitaciones
y los resúmenes de Analytics evitan recomputar el read-model en cada petición.

El cliente Redis se reutiliza por proceso y tiene un circuito fail-open.
`READ_MODEL_CACHE_FAILURE_COOLDOWN_SECONDS` vale 30 segundos por defecto. Ante
un fallo se registra una sola transición `read_model_cache.redis_unavailable`,
se deja de intentar durante el cooldown y las peticiones siguen calculando su
respuesta. Cuando una operación vuelve a funcionar, se registra una sola vez
`read_model_cache.redis_available`. Esa segunda línea confirma la recuperación
del cache; no hay conexión Redis real disponible en esta máquina para probarla
contra un servidor.

## ¿Qué cambio para activar el worker y beat de Celery?

En Render, cree/aplique los servicios declarados
`hotel-chipre-pms-worker` y `hotel-chipre-pms-beat`, con el Redis del Blueprint y
la misma base PostgreSQL. El código ya contiene seis entradas en
`build_beat_schedule()`, pero con la política cerrada que hoy declara el YAML
(`EXTERNAL_EFFECTS_ENABLED=false` y `CONNECTIONS_ENABLED=false`) la agenda queda
vacía; arrancar el proceso por sí solo no las activa. Para ejecutarlas, el
owner debe habilitar explícitamente esa política en el perfil pago y configurar
los proveedores que correspondan. Entonces empiezan a publicarse:

- refresh incremental de facts derivadas cada cinco minutos;
- reconciliación nocturna de facts;
- reportes operativos de la mañana y de la noche;
- procesamiento del outbox de notificaciones cada minuto;
- generación de reportes diarios cada quince minutos.

En el perfil con worker/beat, `SYNC_FACT_REFRESH_ENABLED` debe ser `false` en
el worker, beat y también en el servicio web que recibe las peticiones: el
fallback se ejecuta en el API, no dentro de Celery. El servicio free manual
actual debe conservarlo omitido o en `true`, porque allí el fallback síncrono
es la única materialización disponible. `SYNC_FACT_REFRESH_MAX_DAYS` limita el
fallback a 31 días por defecto y el log
`analytics.sync_fact_refresh.inline` muestra cuándo todavía se está usando.

## ¿Qué cambio para activar MongoDB, Cassandra o Neo4j?

Active sólo el flag y la URL/hosts del datastore correspondiente, después de
un smoke test aislado:

- `MONGO_ENABLED=true` habilita la proyección de auditoría hacia MongoDB;
- `CASSANDRA_ENABLED=true` habilita el histórico temporal de eventos de estado
  de habitaciones y cambios diarios de tarifas;
- `NEO4J_ENABLED=true` habilita la proyección de relaciones de reservas,
  huéspedes, habitaciones, empresas y movimientos.

Los tres flags permanecen `false` por defecto y en Compose. El código de estas
rutas existe, pero no se han ejercitado contra una instancia viva en esta
tarea; necesitan un smoke test de conexión, esquema, escritura, reintento y
aislamiento de hotel antes de confiar en ellas en producción.

## ¿Qué cambio para usar un warehouse o datamart separado?

No active otro warehouse por anticipación. La evaluación de cuatro opciones y
la recomendación de seguir en PostgreSQL hasta medir límites está en
[`docs/decisions/tech-0080-warehouse-options.md`](../decisions/tech-0080-warehouse-options.md).
Las tablas `fact_reservation_daily` y `fact_room_occupancy_daily` ya son el
datamart actual: se derivan de PostgreSQL y conservan el alcance por hotel.
ClickHouse tiene una frontera opcional en el código, pero no hay evidencia aquí
de un proveedor conectado ni de una proyección live confiable.

## ¿Qué cambio para aplicar `render.yaml` como Blueprint?

En Render, seleccione el repositorio y aplique `render.yaml` como Blueprint.
Eso declara el web, Redis/Key Value, worker y beat, además de sus variables y
comandos. No se realizó esa aplicación aquí. La advertencia operativa es que
el servicio live actual fue creado manualmente fuera del Blueprint: aplicar el
archivo no demuestra que ese servicio existente quede adoptado, migrado o
reemplazado automáticamente. Hay que comparar nombres, base, variables
secretas y dominio antes de cualquier cambio humano.

## ¿Qué cambio para migrar de Render a otra plataforma con Docker Compose?

Ejecute `docker compose up` en un host con Docker instalado. Compose ya levanta
PostgreSQL, Redis, MongoDB, Cassandra, Neo4j, API, frontend, worker y beat; el
API, worker y beat reciben los nombres internos `db` y `redis` para sus URLs.
Luego ejecute las migraciones con
`docker compose run --rm backend alembic upgrade head`.

La sintaxis de `docker-compose.yml` se valida en esta tarea, pero Docker no está
instalado en esta máquina: el arranque real, la conectividad entre contenedores,
las migraciones y el ciclo Celery/Redis siguen sin verificación runtime.

## Limitación conocida: `alembic downgrade base`

La cadena histórica de migraciones no puede retroceder hasta `base` en
PostgreSQL. El fallo aparece al retroceder desde
`20260724_core_tenant_composite_fks` hacia
`20260724_payment_proof_blobs`, cuando la migración intenta eliminar una
restricción única de `payments` que todavía tiene claves foráneas compuestas
dependientes:

```text
psycopg2.errors.DependentObjectsStillExist: cannot drop constraint uq_payment_hotel_id_id on table payments because other objects depend on it
```

Esto es una limitación histórica anterior a las migraciones actuales, no un
fallo de la campaña vigente. El test de migraciones de PostgreSQL comprueba el
camino operativo de releases: `upgrade head` desde una base vacía, un segundo
`upgrade head` sin cambios y `downgrade -1` seguido de `upgrade head`. No
comprueba `downgrade base` ni debe repararse esa migración histórica dentro de
esta campaña.

En consecuencia, no se puede reconstruir una base existente caminando las
migraciones hacia atrás hasta cero. Ante una recuperación, restaure un backup o
migre hacia adelante desde una base vacía; no use `downgrade base` como
procedimiento operativo.
