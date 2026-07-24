---
name: scale-data-architecture
description: "Audita y diseña arquitectura de datos multi-tenant para Hotel Chipre PMS: aislamiento por hotel, PostgreSQL OLTP, Redis/Valkey, CDC, warehouse analítico, índices, capacidad y reconciliación. Usar al revisar cambios de base de datos, tarifas, pagos, caja, inventario, reportes, escalado o riesgos de mezcla de datos entre hoteles y pestañas."
---

# Scale Data Architecture

## Propósito

Evaluar y mejorar la arquitectura de datos con evidencia ejecutable. Mantener PostgreSQL como fuente única de verdad para operaciones transaccionales y separar explícitamente caché, eventos y analítica derivada. No aceptar afirmaciones de aislamiento o rendimiento basadas sólo en intención, documentación o una prueba de un único hotel.

## Flujo obligatorio

1. Ejecutar `memoryctl context --project hotel-chipre-pms --agent data-architecture-specialist` y consultar el context pack de base de datos antes de explorar código.
2. Leer `docs/data-foundations/architecture-hybrid.md`, `docs/data-foundations/performance-benchmarks.md` y el reporte Graphify. Si Graphify está desactualizado, marcar las conclusiones dependientes del grafo como `needs-verification` y confirmar en código y tests.
3. Identificar el `hotel_id` derivado del principal autenticado. Nunca tomar el tenant desde un campo libre del body o confiar en un filtro frontend.
4. Formular una hipótesis verificable, agregar o ejecutar una prueba mínima y conservar la salida relevante, consulta, volumen, entorno y `code_sha`.
5. Clasificar cada hallazgo como `confirmed`, `inferred`, `historical` o `needs-verification`; no resolver contradicciones materiales silenciosamente.

## Auditoría de aislamiento

Revisar cada ruta y servicio afectado en estas capas:

- API: autorización, contexto de hotel, filtros y respuestas.
- Servicio: cada lectura/escritura recibe el tenant explícitamente y valida relaciones entre entidades.
- PostgreSQL: claves foráneas compuestas cuando la relación cruza dominios hotel-scoped, índices con `hotel_id` primero y RLS como defensa adicional cuando el despliegue lo soporte.
- Caché/eventos: toda clave, lock, idempotency key y canal incluye hotel; una invalidación no puede afectar otro hotel.
- Frontend: query keys y revisiones incluyen hotel; una pestaña no presenta datos del hotel anterior después de cambiar sesión.

Crear pruebas negativas con dos hoteles y entidades con IDs coincidentes. Exigir denegación o ausencia para lectura, modificación, pagos, disponibilidad, caja, stock, reportes, exportaciones y webhooks cruzados.

## Forward-tests obligatorios

Antes de cerrar una auditoría de arquitectura deben pasar dos contratos
independientes y ejecutables, sin `xfail` ni mocks que oculten el límite:

1. `tests/test_scale_data_architecture_forward.py::test_forward_multi_hotel_context_cannot_read_or_attach_foreign_entities`
   debe probar lectura y escritura con una entidad válida de otro hotel.
2. `tests/test_scale_data_architecture_forward.py::test_forward_stale_tariff_quote_cannot_persist_reservation`
   debe cambiar una tarifa después de emitir la cotización y verificar que la
   reserva no se persiste.

La salida debe conservar el volumen de casos, el entorno y el SHA del código.
Estos forward-tests son una puerta mínima; no reemplazan la matriz completa de
endpoints hotel-scoped ni la validación provider-bound de PostgreSQL/RLS.

## Tarifas y consistencia entre superficies

- Localizar la única función de cotización y comprobar que calendario, habitaciones, reserva rápida, API pública y edición la reutilicen.
- Exigir snapshot inmutable al confirmar reserva, revisión/versionado de tarifas y rechazo de cotizaciones vencidas o modificadas.
- Verificar que el saldo salga del ledger transaccional, no de cálculos duplicados en frontend o reportes.
- Probar dos pestañas: cambiar una tarifa en una, observar invalidación o versión en la otra y confirmar que el servidor rechaza una reserva basada en precio obsoleto.

## OLTP, caché y warehouse

Mantener estas fronteras:

- PostgreSQL: reservas, huéspedes, habitaciones, tarifas, pagos, transacciones, caja, stock, permisos y auditoría.
- Redis/Valkey: sesiones efímeras, rate limits, locks, idempotencia, caché y eventos; nunca fuente de verdad.
- Warehouse: hechos y dimensiones derivados mediante CDC/outbox, sin dobles escrituras de negocio, PII innecesaria ni comprobantes binarios.

Para cada métrica analítica documentar `data_as_of`, lag, fuente, filtros por hotel y reconciliación contra PostgreSQL. Un warehouse atrasado debe informar su antigüedad o bloquear la publicación; nunca aparentar exactitud actual.

## Rendimiento y capacidad

1. Medir primero con datos sintéticos y un entorno aislado: volumen, cardinalidad, distribución por hotel, consultas y versión del código.
2. Usar `EXPLAIN (ANALYZE, BUFFERS)` para consultas calientes y comprobar índices reales, no sólo declarados.
3. Buscar N+1, scans innecesarios, pool agotado, locks largos, cache keys incompletas, consultas sin límites y reportes sobre el primario.
4. Ejecutar carga progresiva y soak con métricas de p95/p99, errores, CPU, memoria, conexiones, locks, lag CDC y reconciliación.
5. Comparar contra SLO explícitos. No declarar soporte para 10.000 usuarios u hoteles si sólo se probó localmente o con datos diminutos.

## Entregable

Entregar un informe breve y reproducible con:

- alcance, entorno y `code_sha`;
- mapa de fuentes de verdad y flujo de datos;
- hallazgos ordenados por dinero/datos, seguridad, integridad, rendimiento y mantenibilidad;
- consulta, test o evidencia que prueba cada hallazgo;
- cambio mínimo recomendado, riesgo y criterio de aceptación;
- resultados antes/después y limitaciones pendientes.

## Límites

- No leer, copiar ni guardar secretos, cookies, tokens, comprobantes reales o PII innecesaria.
- No ejecutar carga, migraciones destructivas ni pruebas mutantes contra producción.
- No hacer que ClickHouse, Redis, una réplica o el frontend sean autoridad de pagos, caja, tarifas o disponibilidad.
- No agregar índices, particiones, réplicas o proveedores por intuición: cada cambio debe tener una consulta, métrica, prueba o umbral que lo justifique.
