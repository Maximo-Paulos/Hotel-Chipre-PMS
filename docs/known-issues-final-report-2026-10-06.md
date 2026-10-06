# Reporte final de fallos conocidos y pendientes de remediación

**Fecha de corte:** 6 de octubre de 2026
**Estado:** abierto; requiere verificación posterior
**Alcance:** ronda 2 de simulación, regresión de CI detectada en PR #125, rendimiento y egreso, decisiones operativas y verificación de producción.

Este documento consolida los hallazgos y estados compartidos hasta la fecha. Separa lo confirmado en código y pruebas de lo que requiere medición, decisión de producto o acceso al servicio desplegado. Un test local, un build publicado o una respuesta HTTP del sitio no se consideran evidencia de QA en producción.

## Estado actual

- La remediación funcional está en el [PR #125](https://github.com/Maximo-Paulos/Hotel-Chipre-PMS/pull/125), rama `codex/fix-ronda-2-week-simulation`, abierto como borrador. El head remoto actual es `c508093c`; la base es `main`. Después de incorporar el código en `2b17bfc3`, los commits `ec0a9400` y `c508093c` actualizaron el estado del reporte y los metadatos de Graphify.
- El CI de ese head informa backend y frontend exitosos, contract exitoso y E2E fallido. El test que falla es `reservation-lifecycle.spec.ts`, en la prueba de voucher cuando el navegador bloquea una ventana. Los gates de release y la evidencia confiable fueron omitidos por tratarse de un draft.
- El commit `2b17bfc3` ya incorpora la corrección del voucher: el botón queda deshabilitado mientras cargan los resúmenes financiero u operativo; la regresión retiene deliberadamente la respuesta operativa, comprueba el estado deshabilitado y luego verifica el aviso de popup bloqueado. La prueba focalizada pasó cinco veces consecutivas. Todavía no hay ejecución de `PR Validation` para este SHA; la corrida previa evaluó `c76452d6` y falló en este flujo.
- También se portó localmente a este worktree la división lazy de rutas públicas/marketing, `AppShell` y master-admin. El build bajó el entry inicial de 773,83 kB (228,54 kB gzip) a 566,91 kB (177,66 kB gzip), aproximadamente 26,7% menos bytes sin comprimir; Vite aún advierte que supera 500 kB.
- Se agregaron localmente el detalle de arqueo por usuario y cobertura para verificarlo en la API. También se fortaleció la regresión del reembolso: una devolución en efectivo debe producir exactamente un egreso de caja ligado a la transacción y reserva. La suite focalizada que cubre esos cambios pasó con 71 pruebas.
- `/health/datastores` ahora informa `blocked` sin conectar a ClickHouse cuando `EXTERNAL_EFFECTS_ENABLED` o `CONNECTIONS_ENABLED` cierra el tráfico de proveedores. Añadí una regresión que falla si el health check intenta crear el cliente en esa configuración.
- El commit `b5cc58c0` está reportado en `main`; su build y publicación de imágenes terminaron. No demuestra que Render esté ejecutando ese SHA.
- La API de producción fue reportada como suspendida por Render (`503`, `suspend-by-user`). No se han verificado persistencia ni flujos funcionales en la nube.
- El checkout de rendimiento, basado en `e172ceb`, conserva sus 59 archivos modificados preexistentes. Tras comparar la divergencia, se portó únicamente la optimización de asignación de habitaciones y su regresión al worktree local del PR; el resto sigue sin integrar ni desplegar. Se preservó el árbol de origen.
- No se hicieron cobros, cambios de facturación, despliegues, escrituras de producción, envíos de correo ni llamadas de webhook.

## Fallos funcionales de la simulación

El PR #125 reúne aproximadamente 191 archivos de remediación para las áreas reportadas:

- concurrencia de pagos, bloqueos y consultas PostgreSQL;
- permisos, cambios individuales de permisos y recuperación de sesión;
- manejo del pool de conexiones y cierre de SSE;
- no-show y tarea programada;
- extensiones de estadía y ajustes individuales de tarifas;
- exportaciones CSV, informes semanales y reporte operativo;
- revisión manual de reembolsos;
- cantidades, costos y reclamos de lavandería;
- recibos por correo e idempotencia;
- mensajes y validaciones en español;
- restricciones de huéspedes y confirmaciones;
- planes de USD 20, 100 y 200, manteniendo checkout sin cobros.

También se añadió una regresión de Playwright para guardar overrides individuales de permisos en `frontend/e2e/settings-custom-role-permissions.spec.ts` (cerca de la línea 458), además de cambios asociados y artefactos de Graphify.

Las categorías anteriores describen trabajo implementado en el PR; no acreditan QA en producción. El CI de `c76452d6` dejó un E2E fallido, detallado arriba. La corrección fue incorporada en `2b17bfc3`; falta una ejecución de `PR Validation` sobre ese SHA.

## Validación conocida

### PR #125 y validación local posterior

- En el SHA `ffa8d580`, el reporte previo registró frontend, backend, E2E Chromium y contratos exitosos: backend 2.987 aprobadas, 34 omitidas y 12 `xfail`; 10 pruebas locales de permisos y una prueba backend focalizada también pasaron.
- Para `c76452d6`, GitHub mostró backend y frontend exitosos, contrato exitoso y E2E fallido en el flujo del voucher. En la secuencia posterior hasta `c508093c`, sólo aparecen el gate confiable omitido por ser draft y el preview; no apareció un run de `PR Validation`, por lo que el cambio del voucher aún carece de CI remoto.
- Matriz E2E local sobre el árbol actual: **207 aprobadas, 6 omitidas y 0 fallidas** (213 casos, 11,8 minutos; código 0). Incluyó Chromium, sitio público, Chromium móvil y routing de preview; pasaron voucher, overrides de permisos, pagos y caja. Las omisiones dependen de realtime, credenciales o infraestructura de carga no disponible en este entorno.
- Backend local completo, repetido tras portar la optimización de asignación y el health check con la política de egreso: **2.990 aprobadas, 34 omitidas y 12 `xfail`**, 59 warnings, en 370,84 segundos; el proceso terminó con código 0.
- Frontend local después de la división lazy: 108 tests Node aprobados; typecheck, lint y build correctos. El entry inicial es 566,91 kB sin comprimir (177,66 kB gzip); Vite aún advierte que excede 500 kB, así que conviene perfilar el resto antes de otra división.
- `tests/test_docs_baseline.py`: 2 aprobadas. Las regresiones focalizadas del reporte diario, pagos, caja y finanzas terminaron con 71 aprobadas; las regresiones de health check con ClickHouse cerrado, con 11 aprobadas. Frontend: 108 tests Node aprobados, typecheck y lint limpios, build exitoso. La matriz E2E del árbol actual terminó con 207 aprobadas y 6 omitidas.
- Graphify AST-only quedó regenerado con 13.894 nodos, 46.318 relaciones y 1.101 flujos; portable-check verificó 352 artefactos después de normalizar 22 rutas y un path de flujo. `graphify check-update` aún señala metadatos semánticos de descripciones/etiquetas pendientes, y el parser local no reconoce tres fuentes Swift; no se completaron con LLM.
- Las validaciones locales incluyen el cambio de código introducido en `2b17bfc3` y mantenido en `c508093c`; las suites completas se ejecutaron antes de empaquetar ese commit y la regresión focalizada pasó cinco repeticiones. Falta el resultado remoto de `PR Validation` en el SHA actual.

### Interpretación de los 12 `xfail` backend

Los 12 `xfail` no son pruebas aprobadas y requieren lectura individual. La revisión posterior del código corrigió una clasificación previa: nueve casos de `tests/test_v72_cash_register.py` son stubs heredados que importan nombres de funciones/endpoints antiguos y no contienen aserciones funcionales. No prueban que falten los flujos descritos. El contrato vigente ya implementa el resumen diario, la exportación del ledger, sesiones de caja y movimientos; además hay cobertura real en `tests/test_cash_register_api.py`, `tests/test_cash_register_service.py` y `tests/test_payment_service.py`. No corresponde agregar aliases antiguos sólo para satisfacer esos imports. Aún conviene reemplazar o retirar esos stubs únicamente cuando quede claro que la cobertura actual representa los requisitos vigentes; revisar específicamente que un reembolso efectivo en efectivo genere el movimiento de caja esperado.

Los tres casos restantes también usan contratos obsoletos: dos esperan la firma/resultados antiguos de extensión de estadía, mientras el contrato actual exige `payment_action` y devuelve `extension_amount`; el otro usa el atributo legado `is_prohibited_stay`, mientras el modelo vigente representa la restricción mediante `GuestTagTypeEnum.PROHIBIDO_ALOJAR`. Hay pruebas del contrato actual en servicios/API y E2E. Revisar si conviene actualizar los casos heredados para probar los contratos actuales. Por lo tanto, no hay evidencia suficiente para presentar los 12 como doce fallos funcionales confirmados ni como deuda equivalente; deben permanecer visibles hasta reconciliar los tests heredados con los requisitos vigentes.

### Optimizaciones en `main` (`b5cc58c0`)

Validaciones reportadas para esa línea: backend 2.895 aprobadas, 35 omitidas y 12 fallos esperados; frontend 91 aprobadas con lint, tipos y build correctos; E2E Chromium 167 aprobadas y 6 omitidas; prueba focalizada en PostgreSQL 16 aprobada; publicación de imágenes completada. No confirman despliegue activo ni QA funcional en Render.

### Mitigaciones locales de rendimiento

En el checkout local de egreso/rendimiento se ejecutaron 107 pruebas focalizadas: telemetría HTTP saliente, límites de listas, telemetría de requests, reportes operativos, asignación, almacén analítico, almacenamiento, API/facts analíticos y conteos de habitaciones. Todas pasaron. Aparecieron warnings SQLAlchemy preexistentes de relaciones solapadas y warnings de dependencias; no hubo fallos.

Después también pasó la suite backend completa de ese checkout base: 2.904 aprobadas, 34 omitidas y 12 `xfail`, 49 warnings, código de salida 0. Esa ejecución valida ese árbol basado en `e172ceb`; no reemplaza la suite del PR, que se volvió a ejecutar por separado.

Las mediciones PostgreSQL sintéticas locales registradas para 25 iteraciones muestran:

| Flujo | Antes | Cambio local | Lectura correcta |
|---|---:|---:|---|
| `daily_report`, p95 | 173,58 ms | 103,79 ms | Mismo conjunto sintético de 1.173 reservas futuras activas; es una medición local, no un SLO de producción. |
| `allocation.build_slots_from_db`, p95 | 216,26 ms | 7,21 ms | Mismas 258 reservas superpuestas en ventana de 45 días; no atribuir toda la diferencia a índices. |
| Ajustes para 1.000 IDs | 10.000 filas leídas: 1,466 ms | 1.000 filas agrupadas: 1,804 ms | Agrupar ahorra 90% de filas entregadas a Python, pero en este fixture agrega ~0,34 ms dentro de PostgreSQL; no prueba una reducción de bytes de red ni justifica un índice compuesto. |

La optimización medida de asignación (`build_slots_from_db`) se portó al worktree local del PR, junto con una regresión que comprueba una sola lectura proyectada de reservas y evita traer `pricing_snapshot` o hacer joins innecesarios. La prueba focalizada de asignación y reportes pasó (13 tests). El resultado sintético de asignación sigue siendo evidencia del checkout local, no de producción.

El entorno fue PostgreSQL 16 efímero con datos sintéticos, sin producción ni base compartida. Los números son señales útiles para esta carga, no evidencia de latencia del proveedor, memoria o ancho de banda real.

## Pendientes funcionales, de producto y de release

### Prioridad inmediata

1. Conseguir y revisar una ejecución de `PR Validation` para `2b17bfc3`, incluido E2E Chromium; revisar también que la limpieza de la reserva de prueba no deje fixtures ocupados.
2. No usar el resultado CI de `c76452d6` como resultado del código actual. `c508093c` contiene la corrección del voucher y la división lazy, pero ambos esperan validación remota.
3. Resolver con el responsable la disponibilidad y el costo de reactivar Render. No cambiar plan ni facturación sin instrucción expresa.
4. Cuando el servicio responda, verificar `/health` y `/build-meta.json`, registrar el SHA servido y luego repetir QA de los flujos/roles autorizados. El login `200` no basta.
5. Completar preview aislado, matriz de personas, evidencia y release gate. No retirar controles por estar el PR en draft.

### Decisiones de producto y operación

1. **Huésped restringido:** falta decidir si un manager con `reservation:prohibition_override` puede cotizar, con auditoría y sin crear reserva automáticamente. La pregunta está pendiente. No asumir una política.
2. **Fiscalidad (R14):** definir el alcance fiscal antes de cerrar cobertura de facturación.
3. **Reclamos a proveedores:** definir base de costos respaldada para lavandería y reclamos, sin inventar importes.
4. **Depósitos:** aprobar política de retención/devolución, causales y responsables.
5. **No-show:** provisionar y verificar el cron/worker programado. El código de barrido no demuestra que exista una tarea activa.

### Estado de QA manual compartido

En Chrome se encontraron sesiones de Dueño, Recepción y Gerencia con errores de conexión y datos que podían estar desactualizados. En Caja había un movimiento de prueba escrito en el formulario; se informó que no se envió ni se borró. Preservar ese estado hasta recibir indicaciones y no tratarlo como transacción persistida.

## Auditoría de datos, rendimiento y egreso

La auditoría de datos fue originalmente de solo lectura sobre `b5cc58c0`, coincidente entonces con `origin/main`. No se ejecutaron consultas ni escrituras en producción. El Graphify consultado por esa auditoría todavía señalaba `e172ceb`, así que los hallazgos se contrastaron contra código y pruebas.

### Hallazgos y estado

1. **Reporte diario y reservas futuras sin límite.** El conjunto de candidatos sigue completo para preservar el contrato, pero el worktree del PR ahora lee sus columnas escalares y calcula saldos antes de materializar objetos ORM. Sólo carga objetos y las relaciones huésped/habitación para reservas que efectivamente aparecen como impagas. Los ajustes se agregan en SQL con `SUM/GROUP BY`. Una regresión confirma que, entre 20 reservas futuras, sólo se materializa la única que debe aparecer en el reporte.

   En PostgreSQL 16 aislado, con 2.000 reservas sintéticas (1.173 candidatas y 1.016 devueltas como impagas), el p95 de `daily_report` en 20 iteraciones bajó de 341,98 ms a 182,89 ms (46,5%). Una medición de una sola llamada registró 33 sentencias y un pico de 18.608.149 bytes asignados por Python según `tracemalloc`; esto no es RSS del proceso. `EXPLAIN (ANALYZE, BUFFERS)` para los candidatos tardó 0,411 ms y eligió un escaneo secuencial en esa tabla pequeña. Son resultados sintéticos locales, no un SLO ni una medida de producción. La salida todavía contiene todas las reservas impagas futuras; decidir paginación o límite necesita preservar explícitamente la visibilidad completa para el operador.
2. **Redis/read-model cache.** `READ_MODEL_CACHE_ENABLED=false` está en la configuración versionada revisada; con esa opción la lectura reconstruye los datos. La configuración activa del proveedor no quedó verificada en esa revisión. El manifiesto `render.yaml` no prueba qué recursos ni plan están activos.
3. **Telemetría de latencia.** El middleware registra duración de request y SQL, cantidad de consultas, una estimación de bytes de SQL/parámetros, longitud de respuesta cuando el servidor la conoce, host de base de datos y cantidad/duración total/máxima de checkouts del pool. `Server-Timing` expone tiempos de aplicación, SQL y checkout. El tiempo de checkout incluye espera, pre-ping y creación de conexión; no es una medición aislada de espera en cola. El tamaño SQL es estimado y no conserva ni registra valores enlazados. Sigue pendiente separar hidratación ORM y serialización, capturar bytes de respuestas streaming, y correlacionar navegador/backend. Esta instrumentación es local hasta que se integre y llegue a un entorno observable; por sí sola no explica los 7,18 GB reportados por Render.
4. **Dashboard.** Los hooks podrían representar hasta nueve solicitudes de datos según permisos. Es un máximo teórico: TanStack Query puede deduplicar solicitudes. Faltan capturas de tráfico e impacto medido.
5. **Índice compuesto de ajustes.** Es una hipótesis a comprobar con planes. La agregación SQL actual conserva filtro de hotel; el plan sintético leyó media tabla y eligió secuencial. No agregar un índice compuesto por intuición.
6. **Pool.** Los valores predeterminados reportados son 8 conexiones más 4 de overflow por proceso y hasta 15 segundos de espera. La rama local incorpora medición por request del conteo y duración de checkouts; aún falta ejecutarla bajo carga representativa y obtener la configuración activa, el límite real de PostgreSQL y el número de procesos. La medición actual no distingue cola de conexión, pre-ping o creación. No se puede atribuir la lentitud al pool ni cambiar sus límites con fundamento todavía.
7. **Aislamiento por hotel.** Los flujos auditados derivan hotel del contexto autenticado y filtran por hotel; una prueba focalizada verifica que los ajustes de otro hotel no se mezclen. Es evidencia solo de esas rutas, no prueba de aislamiento completo ni de RLS desplegado.
8. **Listas y polling.** La rama local acota/pagina historial de pruebas de pago y exportaciones, proyecta columnas necesarias, quita un `commit()` de lectura y reduce polling de pruebas a 30 segundos, pausándolo en pestañas inactivas. Es trabajo local no desplegado.
9. **Egreso de Render y actualización de datos.** Se reportaron 7,18 GB de tráfico `Service-Initiated` y 135 MB de respuestas HTTP en un período con backend suspendido por límite incluido. El manifiesto versionado tiene `CLICKHOUSE_ENABLED=true` y `CLICKHOUSE_REQUIRED=true`, pero configura `EXTERNAL_EFFECTS_ENABLED=false` y `CONNECTIONS_ENABLED=false` en API, worker y Beat. La política de salida cierra el calendario de tareas externas: `build_beat_schedule()` devuelve únicamente el barrido interno de no-show, por lo que **la proyección cada cinco minutos y la reconciliación nocturna no deberían ejecutarse con los valores versionados actuales**. El runbook del repositorio también advierte que esas tareas requieren habilitar explícitamente la política en un perfil pago. No se verificó la configuración efectiva del servicio durante los 7,18 GB; el valor del manifiesto actual no explica por sí solo el tráfico histórico.

   Si en algún entorno se habilita la política, el código programa una ventana analítica móvil de tres días cada cinco minutos y una reconciliación de 366 días cada noche. Cada pasada consulta las filas fuente y puede volver a enviar lotes JSONEachRow a ClickHouse, además de dimensiones. Esto es un mecanismo de egreso repetitivo **condicional**, no una causa probada del consumo reportado. Encontré que `/health/datastores` ignoraba la política cerrada al consultar ClickHouse; el cambio local ya devuelve `blocked` sin hacer la llamada y tiene regresión focalizada. El `healthCheckPath: /health` de Render no llamaba esa prueba. La actualización de facts del API es otro mecanismo: `SYNC_FACT_REFRESH_ENABLED=true` permite recomputar datos en PostgreSQL bajo demanda para ventanas acotadas; no es un envío a ClickHouse. El servicio API fue reportado suspendido, por lo que la frescura actual no se pudo observar. `READ_MODEL_CACHE_ENABLED=false` está en el manifiesto y puede hacer que las lecturas recomputen el read-model; la configuración efectiva sigue sin verificar.

   Evidencia de implementación: [render.yaml](../render.yaml), [política de egreso](../app/services/external_effects_policy.py), [agenda Celery](../app/tasks/celery_app.py), [proyecciones](../app/tasks/analytics_tasks.py), [cliente ClickHouse](../app/services/analytics_warehouse.py), [actualización PostgreSQL bajo demanda](../app/services/analytics_service.py), [health checks](../app/api/health.py) y [runbook de activación](runbooks/enabling-infrastructure.md).

### Medición necesaria para cerrar la auditoría

1. Mantener el benchmark en PostgreSQL local, nuevo y aislado, con datos sintéticos. No apuntarlo a una base compartida sin auditar cómo limpia sus fixtures.
2. Medir cantidad de filas candidatas, número de consultas, p50/p95, memoria y `EXPLAIN (ANALYZE, BUFFERS)` para reporte diario y suma de ajustes.
3. Confirmar el environment efectivo/histórico de Render, incluidos los flags de conexiones, definición de servicios worker/Beat y métricas de ancho de banda por tipo/destino. Revisar logs para saber si existieron proyecciones o llamadas de otro proveedor en el período afectado.
4. Añadir o activar telemetría saliente de privacidad segura alrededor de cada llamada ClickHouse y otros proveedores: destino/host permitido, nombre lógico de integración, bytes de solicitud/respuesta, duración, estado y nombre de tarea; omitir credenciales, parámetros de URL, SQL, payloads y PII. Agregar recuento de filas/bytes por proyección y medir ClickHouse en un destino QA aislado.
5. Revisar el ciclo de actualización de hechos: qué datos requieren CDC, recuperación incremental y reconciliación; determinar el mínimo intervalo/ventana que preserve frescura y reparación de deriva. Validar filas/cuentas antes y después en una base y un almacén sintéticos aislados antes de modificar la programación de Render.
6. Si Render vuelve a estar disponible, correlacionar métricas horarias `Service-Initiated`/HTTP con logs de la tarea, destino, bytes por llamada y configuración efectiva de Redis, procesos y base. El intervalo de Render es horario y no atribuye por sí solo el destino, según [métricas de servicios de Render](https://render.com/docs/service-metrics); el ancho de banda externo iniciado por servicios es facturable según [documentación de egreso de Render](https://render.com/docs/outbound-bandwidth).
7. Medir espera/saturación del pool y separar hidratación/serialización si persiste latencia no explicada por SQL.
8. Tomar cualquier decisión de límites, pool o índices sólo después de tener planes, cardinalidades y resultados reproducibles. El reporte diario conserva el listado completo; si se opta por paginar o limitar la salida, hay que completar primero el contrato de paginación y la navegación frontend para que no se oculten cobros pendientes.

## Próximos pasos ordenados

1. Revisar por qué GitHub no inició `PR Validation` al actualizar el draft y obtener validación para `2b17bfc3` sin retirar el estado draft ni omitir controles.
2. Antes de reactivar Render, cerrar en entorno aislado la medición y el plan de reducción/estabilización del egreso de ClickHouse y demostrar que el refresco analítico conserva integridad y frescura.
3. Resolver las cuatro decisiones de producto/operación pendientes y confirmar el cron de no-show.
4. Resolver disponibilidad/costo de Render con el responsable; una vez activo, verificar SHA y correr QA autorizado.
5. Revisar y portar selectivamente mitigaciones restantes desde el checkout local basado en `e172ceb` a una rama al día con `main`; preservar cambios locales y validar tras integrar. La división lazy y optimización de asignación ya están en el worktree del PR.
6. Completar mediciones de consultas y tráfico saliente en entornos aislados, contrastarlas con evidencia del proveedor y cerrar release gates sólo con la evidencia requerida.

## Seguridad, límites y riesgos

- No se verificó el funcionamiento de los arreglos en producción. No se activó Render, no se modificó facturación y no se enviaron pagos, correos ni webhooks.
- Los cambios del voucher y rendimiento están en el head del PR, pero no tienen aún CI remoto en `2b17bfc3` ni constituyen evidencia de release o QA de producción.
- La suite backend terminó con warnings de SQLAlchemy por relaciones tenant solapadas, deprecaciones del framework y advertencias Pydantic al serializar `Decimal` como `float` en pruebas de OTA. No fallan la suite, pero requieren triage separado antes de afirmar que no hay advertencias de ejecución.
- El build frontend pasa, aunque avisa que el entry chunk excede 500 kB. El gzip es 228,54 kB; no se cambió el chunking sin perfil que identifique el costo real.
- La auditoría de aislamiento cubre rutas específicas; no acredita aislamiento completo del PMS ni configuración RLS activa.
- No hay evidencia actual de percentiles o planes de la base desplegada ni atribución causal del egreso de Render.
- PR #125 permanece draft; los gates de release aparecen omitidos y deben ejecutarse por el proceso normal cuando corresponda.

## Referencias

- [PR #125 — remediación de la simulación](https://github.com/Maximo-Paulos/Hotel-Chipre-PMS/pull/125)
- `docs/data-foundations/performance-benchmarks.md` en el checkout local de mitigaciones, fuente de mediciones sintéticas registradas.
- `docs/data-foundations/recomendacion-arquitectura-datos-2026-10-06.md` en el checkout local de auditoría, fuente del análisis de egreso/arquitectura.
- Checkpoint de continuidad de voucher: `/Users/maximopaulos/AI-Workspace/memory/checkpoints/2026-10-06/20261006-194250-codex-voucher-bloqueado-hasta-cargar-resumen-financiero.md`.
