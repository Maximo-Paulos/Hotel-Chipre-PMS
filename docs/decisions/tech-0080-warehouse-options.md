# TECH-0080 — Opciones de warehouse y recomendación

**Estado:** propuesta para decisión humana; la decisión de la sección 7 sigue abierta.
**Fecha de auditoría:** 2026-08-21
**Código auditado:** `6fd71f0` (`origin/main` en este worktree)
**Alcance:** TECH-0080, con impacto en TECH-0081 y TECH-0082. No implementa ninguna de esas tareas.

## Resumen ejecutivo

El sistema ya tiene una base de analytics en PostgreSQL: dos fact tables hotel-scoped, contratos de hechos, refresh acotado por ventana, un hook de escritura para cambios de reservas y un self-heal cuando un rango aún no fue materializado. El API de Analytics lee esas facts y puede cachear el resumen en Redis.

También existe un límite de ClickHouse en el código, con dimensiones/facts PII-free, `ReplacingMergeTree`, proyección replayable y reconciliación. Es una frontera preparada y config-gated, no evidencia de que haya un proveedor operativo conectado. No hay integración BigQuery en el código auditado. El API actual no consulta ClickHouse.

La escala comercial vigente es pequeña a mediana: el producto declara 1–80 habitaciones por hotel y el catálogo actual codifica límites de 15/40/80. El modelo no impone un máximo global de hoteles ni de reservas; las cifras de 1–100 hoteles, 5–500 habitaciones/hotel y 100–500K reservas/hotel que aparecen en el DER son estimaciones de planificación, no mediciones de producción ni certificación de capacidad.

### Recomendación

Recomiendo que el Product Lead priorice ahora la opción A: conservar PostgreSQL como fuente operacional y de facts, y escalar primero con consultas, índices, materialized views/read models, cache Redis y —sólo si las mediciones lo justifican— una réplica de lectura dedicada. Mantendría el contrato de proyección/reconciliación preparado para una futura opción C o B, pero no introduciría BigQuery todavía.

La razón es doble: el volumen de lanzamiento no demuestra necesidad de otra base y la sección 3.3 del spec exige optimizar PostgreSQL, Redis, materialized views y read models antes de agregar otra DB. La decisión final sigue siendo del humano; esta recomendación no cierra la decisión abierta de la sección 7.

## 1. Estado real verificado en el código

### 1.1 Facts y refresh en PostgreSQL

La migración `20260424_analytics_r1_base` y `app/models/analytics.py` definen:

- `fact_reservation_daily`: una fila por reserva y noche de estadía, con `hotel_id`, reserva, habitación/categoría/empresa, canal, segmento, estado, no-show y métricas de revenue, impuestos, comisiones, costos y margen en ARS/USD. Tiene unicidad `(hotel_id, reservation_id, stay_date)` e índices compuestos por hotel y fecha/dimensión.
- `fact_room_occupancy_daily`: una fila por habitación y noche, con estado nocturno, sellable/occupied, reserva asociada, revenue neto y margen. Tiene unicidad `(hotel_id, room_id, stay_date)` e índices por hotel, fecha, habitación, categoría y estado.

`app/services/analytics_facts.py` reconstruye ambas tablas para una ventana de fechas: borra las filas de esa ventana y vuelve a derivarlas desde reservas, habitaciones, categorías, empresas y eventos de estado. El patrón es incremental por ventana, no un upsert de una sola fila.

El write-path de reservas llama a `touch_reservation_fact_window` para altas, cambios de fechas/habitación/importe, transiciones de estado y operaciones de rebooking/movimiento. El refresh ocurre dentro de un savepoint: un fallo de integridad del refresh no debe deshacer la escritura operacional. La ventana es la estadía afectada, no todo el rango que tenga abierto el dashboard.

El self-heal `_ensure_facts_materialized` se ejecuta en los builders de Analytics cuando no hay ninguna fila de facts para el rango solicitado; reutiliza el mismo refresh y deja que la constraint única resuelva una carrera básica. Esto cubre particularmente el caso de un `/api/analytics/home` consultado antes de que exista materialización.

### 1.2 API, cache y freshness

`app/api/analytics.py` expone, entre otros:

- `/api/analytics/starter-summary`;
- `/api/analytics/home`;
- `/api/analytics/rooms` y detalle por habitación;
- detalle por categoría y empresa;
- segmentos, canales y operaciones;
- exports, alertas e insights/IA sujetos al plan y permisos.

Los payloads de home y starter-summary pueden pasar por `read_model_cache.py`, con claves Redis prefijadas por `hotel_id` e invalidación hotel-scoped. Los demás builders consultan el servicio de Analytics y las facts de PostgreSQL según el caso. Los envelopes exponen `data_as_of`, `source_lag_seconds` y `data_source`; esto evita presentar como actual una fact derivada vieja.

Hay además reportes operativos bajo `/api/reports` que consultan PostgreSQL operacional directamente, incluyendo reservas y transacciones. No son un warehouse ni un data mart separado.

### 1.3 Jobs y la diferencia entre facts PG y proyección ClickHouse

Las tareas Celery `analytics.refresh_fact_reservation_daily` y `analytics.refresh_fact_room_occupancy_daily` existen y están registradas. Sin embargo, el beat definido en `app/tasks/celery_app.py` agenda:

- `analytics.project_all_derived_facts_incremental` cada 300 segundos;
- `analytics.reconcile_all_derived_facts_nightly` diariamente.

Esas dos tareas recorren la proyección operativa a ClickHouse (pagos, caja y stock) y su reconciliación. El helper que recorre todos los hoteles no llama a los dos `refresh_fact_*` de PostgreSQL. La tarea separada de proyectar reservation facts a ClickHouse existe, pero no aparece en el beat mostrado. Por tanto, el estado actual confirmado es:

1. refresh PostgreSQL por write-path de reservas y self-heal en lectura;
2. tareas manualmente invocables para refresh de facts PG;
3. proyección ClickHouse operativa programada sólo cuando el perfil permite conexiones externas;
4. no un pipeline único que garantice, por sí solo, CDC de todas las facts.

Los comentarios de `analytics_service.py` y algunos comentarios de tests todavía describen el problema anterior como si no hubiera hook o beat. El código ejecutable actual debe prevalecer para esta auditoría: el hook existe y el beat de ClickHouse existe, pero no debe confundirse con un refresh programado de las facts PG de reservas/ocupación.

### 1.4 ClickHouse existe como boundary, BigQuery no

`app/services/analytics_warehouse.py` implementa un cliente HTTP y un esquema derivado con:

- dimensiones de hotel, fecha, habitación y categoría;
- reservation, payment, cash movement y stock movement facts;
- particionado por hotel/mes para facts temporales;
- allow-list de columnas que excluye PII de huéspedes de la reservation fact;
- escritura idempotente por versión con `ReplacingMergeTree`;
- reconciliación de conteo y, para facts operativas, conteo más importe.

El cliente devuelve `None` si `CLICKHOUSE_ENABLED` es falso y falla cerrado si se lo exige sin URL. Los defaults de `.env.example` lo dejan deshabilitado. `render.yaml` declara variables para un despliegue que lo exigiría, pero el repositorio no prueba que exista un proveedor real conectado, ni su latencia, lag, coste o reconciliación en producción. `docs/data-foundations/scale-readiness.md` también marca la validación del proveedor como pendiente.

No se encontraron clientes, datasets, jobs ni configuración de BigQuery. No se creó una cuenta ni se consultó ningún proveedor cloud.

### 1.5 Qué cubre y qué no cubre hoy

| Área | Estado verificado |
|---|---|
| Analytics hotel-scoped de reservas, ocupación, canales, segmentos, empresas y operaciones | Existe en API y se deriva de PostgreSQL/facts PG. |
| Revenue/margen de hotel | Existe en facts y payloads, sujeto a las definiciones actuales del contrato. |
| Freshness visible | Existe metadata de `data_as_of`/lag; no es una certificación de lag de proveedor. |
| Cache/read model | Redis read-through para resumen; fallback a PostgreSQL. |
| Fact tables incrementales | Existe refresh por ventana y write-time hook; el refresh reconstruye la ventana completa. |
| ClickHouse | Boundary y tareas de proyección/reconciliación implementadas; proveedor y consumo del API no verificados. |
| BigQuery CDC/ELT | No existe en el código auditado. |
| Hotel Analytics Data Marts formalmente separados | No existe todavía el bloque TECH-0081 como marts versionados de warehouse. |
| SaaS Owner Data Mart | No existe. Master Admin tiene un summary operativo de hoteles/suscripciones, pero no el mart de uso, MRR/ARR, churn, API/storage/IA/integraciones/jobs/errores requerido por TECH-0082. |

## 2. Escala real estimada hoy

### 2.1 Lo que el modelo permite

`HotelConfiguration.id` es una clave entera por hotel, sin límite global en el modelo. `Reservation.id` es entero autoincremental y cada reserva lleva `hotel_id`, claves foráneas compuestas e índices por hotel/fechas. Esto permite múltiples hoteles y muchas reservas lógicamente; no significa que la instalación actual haya demostrado soportar un número concreto.

El producto define para el lanzamiento un rango de 1–80 habitaciones por hotel. El catálogo vigente en código define `starter=15`, `pro=40` y `ultra=80` habitaciones, además de límites de staff 3/8/20. La enforcement de suscripción está desactivada por defecto, por lo que esos valores son límites comerciales/configurables del flujo, no una cota física de PostgreSQL.

El DER documenta como estimación de planificación 1–100 hoteles, 5–500 habitaciones/hotel, 100–100K huéspedes/hotel y 100–500K reservas/hotel. Es una referencia de diseño, no un conteo de filas real ni evidencia provider-bound. La diferencia entre 80 habitaciones de lanzamiento y 500 del DER debe tratarse como dos perfiles: lanzamiento comercial y estrés futuro.

### 2.2 Crecimiento de las facts

La ocupación crece aproximadamente con `habitaciones × días materializados`, mientras que la reservation fact crece con `reservas × noches de estadía`. Por ejemplo:

| Perfil | `fact_room_occupancy_daily` por hotel/año | En 100 hoteles |
|---|---:|---:|
| 80 habitaciones, lanzamiento | 29.200 filas | 2,92 millones |
| 500 habitaciones, estimación DER | 182.500 filas | 18,25 millones |

Las cifras son aritmética del modelo, no mediciones. Tampoco incluyen índices, facts de pagos/caja/stock, histórico adicional, reintentos de proyección ni snapshots. En el perfil de lanzamiento, estos volúmenes no hacen evidente que BigQuery sea necesario; el cuello puede aparecer antes por queries, concurrencia, refresh o aislamiento que por almacenamiento bruto.

No hay una base de datos productiva disponible en este worktree para contar hoteles, reservas o filas de facts. En consecuencia, “volumen actual” significa aquí límite/modelo/documentación versionada, no inventario live.

## 3. Opciones evaluadas

### Opción A — PostgreSQL facts + materialized views/read models

**Descripción.** Consolidar el patrón ya existente: PostgreSQL autoritativo, facts hotel-scoped, consultas set-based e índices, materialized views o read models para agregados costosos, Redis para cache y una política explícita de refresh/reconciliación. Una réplica de lectura puede agregarse como etapa posterior de esta opción, no como cambio de fuente de verdad.

**Trade-offs concretos.**

- **Costo operativo:** bajo al inicio; se reutilizan la base, backups, observabilidad y conocimientos actuales. Materialized views, almacenamiento de facts e índices aumentan CPU/IO y espacio, pero no agregan otro proveedor obligatorio.
- **Mantenimiento:** medio. Hay que corregir el gap entre refresh por write-path, self-heal y jobs; definir ventanas, backfill, idempotencia, invalidación y métricas de refresh. El refresh actual hace delete+rebuild de la ventana y el occupancy fact recorre `rooms × days`, por lo que deben medirse tiempos y locks.
- **Lock-in:** bajo. SQL, contratos de hechos y PostgreSQL son portables; una futura réplica o warehouse puede leer los mismos contratos.
- **Migración futura:** favorable si los facts se mantienen PII-minimal, con `hotel_id`, lineage, version y reconciliación. Exportar hechos ya modelados es más fácil que reconstruirlos desde tablas operacionales ambiguas.
- **¿Hace falta ahora?:** sí, como camino inmediato y exigido por la sección 3.3 antes de otra DB. No prueba capacidad ilimitada: exige benchmark co-localizado y límites de ventana.

**Riesgo principal.** Consultas históricas cross-tenant, ad hoc o agregados muy amplios pueden competir con el OLTP si no se aíslan. Una réplica de lectura reduce carga de lectura, pero no convierte PostgreSQL en un motor columnar ni resuelve por sí sola la semántica de marts.

### Opción B — CDC/ELT hacia BigQuery

**Descripción.** Mantener PostgreSQL como fuente de verdad, capturar cambios mediante CDC/outbox, cargar staging/raw en BigQuery y publicar transformaciones versionadas hacia marts de hotel y plataforma.

**Trade-offs concretos.**

- **Costo operativo:** medio a alto y variable: proyecto cloud, datasets, jobs CDC/ELT, almacenamiento histórico, consultas, transferencia, monitoreo y presupuesto. El costo puede ser razonable a gran escala, pero no es cero durante un piloto pequeño.
- **Mantenimiento:** alto. Requiere contratos de esquema, backfills, deduplicación/idempotencia, late-arriving events, borrado/retención de PII, lineage, reconciliación PG↔warehouse y alertas de lag. Hoy no existe ese pipeline en el repo.
- **Lock-in:** medio a alto: BigQuery SQL, particionado, IAM, billing y servicios CDC/ELT de Google crean dependencia operativa, aunque el modelo dimensional se puede exportar.
- **Migración futura:** buena para analytics cross-tenant y largos históricos si se diseña el raw con neutralidad y se conservan hechos canónicos en PG. La salida sigue requiriendo exportar datasets, transformaciones y metadatos.
- **¿Hace falta ahora?:** no está demostrado para 1–80 habitaciones por hotel y la escala estimada de 1–100 hoteles. Es más defendible cuando el problema medido es analítico cross-tenant/histórico o cuando PostgreSQL ya no cumple SLO tras optimización y aislamiento.

**Riesgo principal.** Adelantar BigQuery puede convertir una decisión de arquitectura objetivo en costo fijo y superficie de seguridad antes de que TECH-0081/0082 tengan definiciones, fuentes y ownership cerrados.

### Opción C — ClickHouse como warehouse/read model derivado

**Descripción.** Usar la frontera ClickHouse ya presente en el código: hechos PII-free, particionados por hotel/mes, proyección replayable desde PostgreSQL y reconciliación antes de publicar datos. Puede operar como read model de alto volumen sin reemplazar PostgreSQL.

**Trade-offs concretos.**

- **Costo operativo:** medio: proveedor administrado o cluster propio, conexión segura, backups/retención, monitoreo y operación de ClickHouse. Puede ser menor que una plataforma ELT completa, pero agrega una base ya desde ahora.
- **Mantenimiento:** medio a alto. Hay que completar la entrega confiable (CDC/outbox o trigger, replays, deletes/correcciones, `ReplacingMergeTree`/`FINAL`, alertas, contratos de dimensiones y reconciliación). El código local ya cubre parte del boundary, no la validación del proveedor ni el consumo del dashboard.
- **Lock-in:** medio. El modelo de hechos es portable, pero tipos, engines, materialized views y consultas de ClickHouse son específicos.
- **Migración futura:** intermedia. Facilita descargar agregados de alto volumen; migrar luego a BigQuery exige reescribir ingestion/SQL y volver a validar freshness/costes. Mantener PG como autoridad limita el costo de salida.
- **¿Hace falta ahora?:** no para el perfil de lanzamiento salvo que un benchmark demuestre que PG optimizado no alcanza. Es una alternativa más coherente que BigQuery si el problema futuro es agregación rápida de hechos temporales, no necesariamente un ecosistema ELT amplio.

**Riesgo principal.** El repositorio puede dar una falsa sensación de “warehouse listo”: `CLICKHOUSE_ENABLED` está desactivado en defaults y el API de Analytics no lee ClickHouse. La integración provider-bound y la proyección de reservation facts deben probarse antes de llamarla solución activa.

### Opción D — Réplica PostgreSQL dedicada para analytics

**Descripción.** Mantener facts/materialized views en PostgreSQL, pero enviar lecturas analíticas a una read replica o instancia PostgreSQL dedicada mediante réplica nativa/servicio administrado.

**Trade-offs concretos.**

- **Costo operativo:** bajo a medio: segunda instancia, almacenamiento, backups, monitor de replication lag y routing de lecturas. Menor que ClickHouse/BigQuery si ya existe operación PostgreSQL.
- **Mantenimiento:** medio. Hay que controlar lag, consistencia de lecturas, refresh de materialized views, failover y consultas accidentalmente dirigidas al primario. No elimina la necesidad de modelar facts.
- **Lock-in:** bajo a medio, según el proveedor; mantiene PostgreSQL y SQL conocidos.
- **Migración futura:** favorable hacia ClickHouse o BigQuery porque conserva facts SQL y contratos. No resuelve por sí sola consultas columnar/ad hoc muy grandes.
- **¿Hace falta ahora?:** sólo si telemetría demuestra que las lecturas analíticas compiten con el OLTP. La réplica no debe ser la primera respuesta si faltan índices/materialized views/read models.

**Riesgo principal.** Una réplica atrasada puede mostrar analytics stale. Debe exponerse `data_as_of`/lag y nunca usarse como fuente autoritativa para reservas, pagos o disponibilidad.

## 4. Recomendación y criterio para decidir después

### Recomendación actual: A, con una ruta de salida explícita

El camino recomendado al Product Lead es:

1. tomar como base los facts PostgreSQL ya existentes;
2. corregir y medir el ciclo de refresh, backfill, invalidación y reconciliación;
3. mover agregados repetidos a materialized views/read models y conservar Redis para lecturas cacheables;
4. ejecutar benchmark co-localizado con PostgreSQL sobre el perfil de lanzamiento y un perfil de estrés documentado;
5. considerar D sólo si el primario muestra contención de lecturas; considerar C si el problema es volumen/latencia de hechos temporales; considerar B si el problema es gobierno, histórico y analytics cross-tenant a escala de plataforma.

Esta recomendación respeta la sección 3.3: antes de otra DB hay que optimizar query, índices, búsqueda PostgreSQL, Redis, materialized views y read models. No recomiendo fijar un umbral de hoteles o reservas únicamente por intuición: la decisión debe cruzarse con p95 de Analytics (<1 s), query budgets, CPU/IO/locks/pool wait, tiempo de refresh, lag de réplica/warehouse, crecimiento de almacenamiento y costo mensual.

La opción B gana valor cuando TECH-0082 necesite series históricas y agregados de plataforma que no deben recorrer el OLTP de cada hotel. La opción C gana valor cuando el workload sea predominantemente hechos temporales y agregaciones de gran volumen con baja necesidad de una plataforma ELT general. Ninguna necesidad está probada en el perfil actual por el código auditado.

## 5. Qué desbloquea cada opción

| Opción | TECH-0081 — Hotel Analytics Data Marts | TECH-0082 — SaaS Owner Data Mart |
|---|---|---|
| **A. PG facts/read models** | Desbloquea ocupación, ADR, RevPAR, estadía, revenue/margen, categoría, canal, cancelación/no-show y comparaciones a partir de las facts actuales, con tenant scope y freshness visible. Requiere versionar definiciones y ampliar hechos/dimensiones donde hoy falten nacionalidad, recurrencia o margen completo. | Permite un read model agregado en PostgreSQL para hoteles, plan/status, rooms/staff, reservas y métricas operativas del control plane. Necesita fuentes adicionales para API, storage, IA, integraciones, jobs, errores y MRR/ARR; no debe devolver movimientos internos ni PII de huéspedes. TECH-0071 sigue siendo dependencia de autorización y billing. |
| **B. BigQuery CDC/ELT** | Desbloquea marts centralizados, staging/raw, lineage, transformaciones versionadas y consultas históricas/cross-hotel con menor presión sobre el OLTP. Requiere definir CDC/outbox, contratos, retención, PII mínima y reconciliación antes de publicar. | Es la opción más completa para un mart agregado de plataforma: active/trial/churn, plan, uso y MRR/ARR con series históricas y snapshots. Aun así, no crea por sí sola las fuentes: TECH-0071 debe emitir estados/comercial y cada dominio debe registrar uso, jobs y errores de forma consistente. |
| **C. ClickHouse derivado** | Desbloquea lectura rápida de facts temporales de reservas, pagos, caja y stock si se completa la entrega y el API aprende a consumir sólo datos reconciliados. Las dimensiones/facts PII-free ya tienen boundary local, pero el proveedor y la reservation-fact projection no están verificados. | Puede servir para agregados de uso de plataforma a gran volumen, pero hoy no proyecta las entidades necesarias de Master Admin/subscriptions/usage. Requiere nuevas dimensiones, gobierno cross-tenant y reglas de PII; no queda desbloqueado sólo por activar el cliente existente. |
| **D. Réplica PG analytics** | Desbloquea separación de carga de lectura con el menor cambio de modelo, siempre que los marts sean materialized views/read models y se exponga el lag. No resuelve históricos o consultas arbitrarias por sí sola. | Permite un resumen de plataforma pequeño si el volumen cabe en PostgreSQL, pero no es una respuesta fuerte para series históricas, churn complejo o analítica ad hoc multi-tenant. |

## 6. Decisiones que debe tomar el humano

Para cerrar la entrada de la sección 7, el Product Lead debería confirmar:

- si acepta A como camino inmediato sin cerrar la puerta a B/C;
- qué perfil de escala quiere financiar y medir: lanzamiento 1–80 habitaciones o estrés DER de hasta 500 habitaciones/100 hoteles;
- qué métricas de TECH-0082 son obligatorias en la primera versión y qué fuentes se consideran canónicas;
- presupuesto operativo mensual y tolerancia a lag para hotel analytics y owner analytics;
- si el requisito de freshness de warehouse del SLO catalog (p95 <30 s, máximo 60 s) aplica desde la primera entrega de TECH-0080 o sólo después de contratar un warehouse;
- cuándo habilitar un proveedor externo y quién acepta su costo, seguridad, retención y lock-in.

Hasta esas respuestas y mediciones, la recomendación es mantener la decisión **abierta**, implementar sólo el alcance que el Product Lead autorice y no presentar ClickHouse/BigQuery como warehouse certificado.

## Fuentes y nivel de certeza

**Confirmado por código en `6fd71f0`:** `app/models/analytics.py`, `app/services/analytics_facts.py`, `app/services/analytics_service.py`, `app/api/analytics.py`, `app/services/read_model_cache.py`, `app/tasks/analytics_tasks.py`, `app/tasks/celery_app.py`, `app/services/analytics_warehouse.py`, `app/models/hotel_config.py`, `app/models/reservation.py`, `app/models/room.py`, `app/services/subscription_entitlements.py`, `app/master_admin/router.py`.

**Confirmado por documentación/tests locales, no por proveedor:** `docs/HOTEL_PMS_MASTER_DEVELOPMENT_SPEC.md` (secciones 3.3, 4, 7 y TECH-0080/81/82), `docs/analytics-r1.md`, `docs/data-foundations/architecture-hybrid.md`, `docs/data-foundations/der-conceptual-model.md`, `docs/data-foundations/scale-readiness.md`, `docs/data-foundations/slo-catalog.md`, `docs/product-definition.md`, `tests/test_analytics_facts.py`, `tests/test_analytics_task_schedule.py`, `tests/test_analytics_warehouse.py`.

**Needs-verification antes de cerrar:** conteos live de hoteles/reservas/facts, capacidad y p95 PostgreSQL, ejecución real de Celery/beat, proveedor ClickHouse conectado, lag/reconciliación provider-bound, costo mensual y cualquier CDC existente fuera del repositorio.

No se modificó código de aplicación, no se agregaron dependencias, no se creó infraestructura y no se tomó la decisión final de la sección 7.
