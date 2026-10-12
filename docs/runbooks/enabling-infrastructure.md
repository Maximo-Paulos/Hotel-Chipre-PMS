# Perfil SQL-only de Render con presupuesto máximo de USD 25

El perfil local de `render.yaml` propone un workspace Hobby con una API Starter
(0,5 CPU/512 MB) y un Cron Starter que ejecuta el barrido SQL de no-show cada
cinco minutos. El costo fijo estimado es USD 8/mes antes del egress. No declara
Redis/Key Value, worker, Beat ni ClickHouse. Render sigue suspendido y no se
aplicó el Blueprint ni se cambió la facturación.

Render incluye 5 GB de egress compartidos en Hobby y cobra USD 0,15/GB de
exceso. No hay un tope general que garantice que la factura total quede debajo
de USD 25; el consumo debe monitorizarse. [Precios de Render](https://render.com/pricing)
· [Ancho de banda saliente](https://render.com/docs/outbound-bandwidth)

## Interpretar `/health/ready` en perfil SQL-only

`ready=true` y HTTP 200 significan que PostgreSQL responde y las escrituras
críticas conservan un mecanismo de lock seguro. Si Redis no responde, el lock
puede degradar a `postgres_advisory_xact_lock`; la caché de read-models calcula
desde PostgreSQL y SSE usa el outbox de PostgreSQL. En ese caso se debe observar
`redis.status=error`, `critical_lock.status=degraded` y
`optional_degraded=true` cuando haya caché, realtime o locks opcionales
habilitados. Esto no justifica por sí solo subir de plan: Redis agrega costo y
el core mantiene su fallback; primero hay que medir latencia y carga de base.

## ¿Qué cambio para activar Redis y el cache de read-models?

El flujo SSE de invalidación no queda inutilizable si Redis/Valkey está caído:
el backend puede leer el outbox confirmado de PostgreSQL mediante el fallback
acotado de `REALTIME_EVENTS_FALLBACK_POLL_SECONDS`. Redis/Valkey sigue siendo
recomendado para fan-out de baja latencia entre workers, locks, Celery y la
coedición WebSocket.

El polling PostgreSQL usa 5 segundos por defecto y no puede superar ese valor.
Esto reduce un 60% la frecuencia de sondeo frente a 2 segundos (de 30 a 12
lecturas por minuto por stream inactivo), dejando cinco segundos del presupuesto
de frescura para la consulta y actualización del cliente. Los clientes sin SSE
conservan su recuperación HTTP cada 5 segundos mientras el servidor responde;
ante errores, ese fallback aplica backoff hasta 30 segundos para no intensificar
una degradación.

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

Las lecturas de Analytics nunca reconstruyen facts ni tienen un flag para
habilitar esa reconstrucción. Las mutaciones normales mantienen sus facts en
la misma transacción. Los backfills históricos/out-of-band se ejecutan como
operación explícita, con vista previa y alcance revisado mediante
`scripts/repair_analytics_facts.py`.

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
ClickHouse tiene una frontera opcional en el código, pero queda apagado en el
perfil hasta USD 25. No hay evidencia aquí de un proveedor conectado ni de una
proyección live confiable.

## ¿Qué cambia al aplicar `render.yaml` como Blueprint?

El archivo declara una API Starter y un Cron Starter SQL. No se realizó esa
aplicación aquí. El servicio existente fue creado fuera del Blueprint y Render
está suspendido; aplicar el YAML puede crear/adoptar recursos con nombres y
configuración distintos, ejecutar migraciones o iniciar una API contra la base
configurada. Antes de cualquier cambio humano hay que comparar servicios,
región, Supabase URL, variables secretas, dominio, egress acumulado y el modo de
listener. El YAML local no es autorización para reactivar ni desplegar.

## ¿Qué cambio para migrar de Render a otra plataforma con Docker Compose?

Ejecute `docker compose up` en un host con Docker instalado. Compose ya levanta
PostgreSQL, Redis, MongoDB, Cassandra, Neo4j, API, frontend, worker y beat; el
API, worker y beat reciben los nombres internos `db` y `redis` para sus URLs.
Luego ejecute las migraciones con
`docker compose run --rm backend alembic upgrade head`.

El perfil Render SQL-only no depende de Docker; la sintaxis de
`docker-compose.yml` mantiene la infraestructura general de desarrollo. El
arranque real, la conectividad entre contenedores, las migraciones y el ciclo
Celery/Redis siguen sin verificación runtime para ese Compose.

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
