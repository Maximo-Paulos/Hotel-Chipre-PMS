# QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE

## Resumen ejecutivo

- PR #117 está integrado: GitHub lo marca como `MERGED` y su merge commit es ancestro de `origin/main`.
- La app pública sirve `0174f497cc615550c21ba5c78bac0b6893729c7b` tanto desde `/health` como desde `/build-meta.json`; PR #117 está incluido en ese SHA.
- PR #119 es una mejora posterior, sigue abierto en `182dff63530d41c8b8d792b977e7b6401dd4b09c` y no está desplegado.
- Se hizo un recorrido visible de solo lectura con Dueño y Recepción. Gerencia y los demás roles no estaban disponibles en las sesiones abiertas; no se puede afirmar cobertura de todas las cuentas.
- En un re-chequeo, Recepción vio timeout en `/reservas` y fallo al cargar la bandeja operativa; esos errores siguen pendientes y el cambio local aún no está desplegado.
- `/health/ready` informa `READ_MODEL_CACHE_ENABLED=true` efectivo con Redis desconectado, aunque el manifiesto de `main` especifica `false`. El cambio local al default reduce este desajuste solo si el servicio no tiene un override explícito.
- No se escribieron cobros, gastos, permisos ni reservas, y no se enviaron correos ni webhooks. La app compartida muestra datos QA junto con otros registros, sin evidencia de aislamiento de tenant.

## Alcance y entorno

Catálogo: `production-labelled-shared-sandbox-operational`; `release_gate_eligible=false`. Este reporte sirve para diagnóstico operativo; no puede aprobar ni reemplazar la puerta formal de release.

Reconsulta de servicio: **2026-10-05 06:01 ART (UTC-03)**. Se usaron únicamente sesiones abiertas de Dueño y Recepción. El inventario de Chrome no mostró una sesión activa de Gerencia, Codueña, Limpieza o master-admin.

## Servicio desplegado

- API `GET /health`: HTTP 200, `status=ok`, SHA `0174f497cc615550c21ba5c78bac0b6893729c7b`.
- Frontend `GET /build-meta.json`: HTTP 200, mismo SHA.
- `GET /health/ready`: `ready=true`; PostgreSQL conectado. Redis está habilitado pero desconectado (`Redis healthcheck failed`); la verificación informa lock crítico seguro con `postgres_advisory_xact_lock` y estado degradado opcional.
- `GET /health/datastores`: PostgreSQL conectado; Redis desconectado; ClickHouse, Mongo, Cassandra y Neo4j deshabilitados.
- PR #117: merge commit `e36f1d90daf415858fb4a44cdcacdca17d4a750c`, integrado antes del SHA desplegado.
- PR #119: abierto, HEAD `182dff63530d41c8b8d792b977e7b6401dd4b09c`; no está en el servicio.

## Observaciones visibles

| Rol | Recorrido de solo lectura | Resultado | Cobertura |
|---|---|---|---|
| Dueño | Panel, detalle lateral de reserva y Caja | Las pantallas cargaron. No se guardaron cambios ni se enviaron formularios. Se omitieron del reporte nombres e importes visibles. | Parcial |
| Recepción | Habitaciones, Reservas y Tareas / pase de turno | Se observaron 39 habitaciones y 33 reservas. Tareas pasó por carga y mostró un pendiente QA resuelto con autor y hora visibles. | Parcial |
| Gerencia | No había sesión activa disponible en el inventario | No probado en este recorrido. | Bloqueado |
| Codueña, Limpieza, master-admin | No había sesión activa disponible | No probados. | Bloqueado |

Los registros QA aparecen junto a registros de aspecto ordinario en el entorno compartido. No se demostró que el conjunto visible pertenezca a un tenant aislado y desechable; por eso se evitó alterar el ledger, las reservas y la configuración. Una navegación de tarea no permite calcular p50/p95/p99 ni demostrar capacidad.

### Rechequeo visible adicional — 2026-10-05 10:02 ART

- En la sesión autenticada de Recepción, `/reservas` mostró “No se pudo cargar: La solicitud tardó demasiado” en el listado y “No se pudo consultar la bandeja operativa”. La pantalla mantenía un listado parcial; no se interpretó como carga exitosa. No se pulsaron los botones de reintento ni acciones de reserva.
- En una sola recarga controlada de esa vista, el navegador midió `GET /api/rooms/categories` **8,826 ms**, `GET /api/rooms/` **4,727 ms**, `GET /api/reservations/actions/pending` **4,430 ms** y `GET /api/room-movement-groups/` **3,117 ms**; todos respondieron HTTP 200. `GET /api/reservations/` tuvo dos muestras de **1,296 ms** y **2,826 ms**, ambas HTTP 200. Los errores visibles persistieron al terminar la carga. Son tiempos navegador-a-API de una sola pasada, no latencias de SQL ni percentiles.
- La pestaña previa de `/operacion/tareas` mostró una página de error del navegador (`ERR_FAILED`); no permite atribuir el fallo a la API. Una recarga de lectura no produjo evidencia automatizable adicional. No se inició sesión ni se modificaron datos.
- En la sesión Dueño, Caja terminó de cargar; no se abrió ningún formulario ni se cambió el contenido.
- La lectura fresca de `/health/ready` reportó `redis.cache_enabled=true` y Redis desconectado. El `render.yaml` tanto de `origin/main` como de la rama declara `READ_MODEL_CACHE_ENABLED=false`; el valor efectivo proviene del proceso desplegado, pero su origen (override del servicio o variable ausente con default de la app) no se confirmó.
- Ninguna lectura adicional produjo escrituras. Se omitieron del reporte importes, nombres y códigos de reservas visibles.

## Rendimiento y límites técnicos

- Redis desconectado puede degradar lecturas hacia PostgreSQL y el realtime. Un análisis de arquitectura en paralelo observó que el fallback SSE consulta el outbox por pestaña aproximadamente cada 2 segundos; el número real de pestañas, carga, retención y costo de consulta no se midieron.
- PR #119 reduce intentos repetidos de publicación en algunas escrituras durables. No hay evidencia todavía de su efecto de latencia en producción ni de una prueba PostgreSQL con `FORCE ROW LEVEL SECURITY`.
- Los agentes revisaron los caminos de las cinco rutas medidas. En esta rama, `pending` ya usa consultas por lotes y tiene pruebas de cantidad de consultas constante; no se cambió esa lógica. El selector de candidatos todavía evalúa todas las reservas terminales históricas antes de aplicar el límite, por lo que puede crecer con el historial, pero no se midió ese volumen y no se cambió por riesgo semántico.
- Se preparó un parche local para las rutas de categorías y habitaciones: el precio vigente se resuelve en dos consultas por lote en vez de tres consultas por categoría, manteniendo `DailyRate > PricePeriod > precio base`; ambas listas evitan cargar relaciones que su respuesta no serializa. La lista de movimientos conserva sus eventos, pero ya no carga relaciones joined de reservas, habitaciones y usuarios que el DTO no muestra.
- No se repitió la medición de navegador después del parche: no está desplegado. Por eso todavía no se afirma que haya bajado la latencia ni que haya desaparecido el timeout visible.
- No se atribuye la degradación a una sola causa y no se afirma saturación sin métricas.

## Validación automatizada conocida

- Suite backend local completa: **2.851 passed, 34 skipped, 12 xfailed**, 50 warnings, ejecutada antes de estos cambios sobre PR #119 en `182dff63530d41c8b8d792b977e7b6401dd4b09c`.
- Suite backend focal local ejecutada antes de estos cambios: **55 passed**.
- Playwright local focalizado: **11 passed**, en base aislada local.
- Workflow `37283925218` para el mismo HEAD de PR #119 terminó con backend, frontend y E2E aprobados.
- El workflow PR `37283929504`, intento 2, terminó a las 06:10 ART con backend y frontend aprobados, **176 E2E passed y 6 skipped** (16,1 min). El intento anterior tuvo seis fallos E2E; el reintento no reprodujo esos fallos. También pasó el workflow `37283925218` para el mismo HEAD.
- En el log E2E aparecieron advertencias reiteradas `realtime_events.post_commit_publish_failed` mientras Redis no estaba disponible. La suite terminó aprobada; esto no mide la latencia real del servicio.
- Las comprobaciones `operating-system` y `trusted-base-evidence` de PR #119 fallaron porque ambas encontraron **cero** resúmenes QA elegibles. La regla exige evidencia de preview aislado ligada al SHA; este recorrido compartido no satisface ese requisito. No se configuró ni usó Render QA, según la instrucción del propietario, y no se creó evidencia ficticia.
- Ninguna prueba local de SQLite demuestra comportamiento real de PostgreSQL con RLS forzada.
- Tras el cambio local de configuración, los módulos afectados `tests/test_datastores_health.py` y `tests/test_read_model_cache.py` pasaron: **22 passed**. No conectaron a PostgreSQL ni Redis.
- Con los cambios locales actuales, pasaron **64 pruebas** de habitaciones/categorías, movimientos, tarifas diarias/calendario y acciones pendientes. Las regresiones nuevas verifican precedencia de tarifas con dos consultas batch, ausencia de lecturas implícitas de relaciones no incluidas y conservación del JSON de eventos de movimiento. Base SQLite local; no usaron PostgreSQL/Redis.
- `graphify update .` regeneró `GRAPH_REPORT.md` y los inventarios. El extractor no tiene gramática para tres archivos Swift de iOS; esto no impidió actualizar el grafo del resto del repo.

## Cambios externos y límites

- No se registraron cobros ni gastos, no se cambiaron reservas, tarifas, permisos ni ajustes.
- No se enviaron correos, ni se activaron webhooks u OTAs.
- No se probaron acciones financieras sobre el dominio compartido porque no se verificó aislamiento de tenant y el estado de caja visible pertenece a datos persistentes.
- El recorrido compartido no reemplaza la matriz formal por roles, las pruebas PostgreSQL/RLS ni la puerta de release.
