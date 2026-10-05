# QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE

## Resumen ejecutivo

Se comprobó de forma visible el despliegue posterior al cierre del PR #117 usando solo las sesiones abiertas de Dueño, Gerencia y Recepción. `/health` y `/build-meta.json` informan el mismo SHA integrado: `e36f1d90daf415858fb4a44cdcacdca17d4a750c`.

El Dashboard terminó de cargar para Dueño y Gerencia. Caja cargó en Dueño, pero la sesión de Gerencia recibió acceso denegado; queda pendiente cotejarlo con los permisos efectivos configurados para ese hotel. En Recepción, el detalle de una reserva marcada `QA-OP` abrió, pero el resumen financiero mostró un error persistente. El aislamiento de esa reserva no está verificado. La solicitud de solo lectura a `/api/payments/summary/{reservation_id}` devolvió HTTP 403 en los intentos observados. El rol tiene `cash:operate` en la matriz predeterminada del código; no se pudo verificar si la cuenta del hotel tiene una anulación personalizada. No se registraron cobros, gastos ni cambios de reserva.

La preparación del backend figura lista con Postgres conectado y Redis desconectado en modo degradado. Esto coincide con un riesgo de latencia en la publicación de eventos después del commit. El arreglo local de refresh analítico dirigido reduce trabajo de escritura, pero todavía no está desplegado. Esta navegación no mide una escritura real en la nube.

## Cobertura observada

| Rol | Área | Observación | Estado |
|---|---|---|---|
| Dueño | Dashboard | Los estados de carga inicial terminaron y quedaron visibles los indicadores y la bandeja operativa. | PASS |
| Dueño | Caja | Cargaron resumen diario, conciliación por turno, movimientos y controles de cierre. No se ejecutó ninguna acción. | PASS, lectura solamente |
| Gerencia | Dashboard | Los estados de carga terminaron y quedaron visibles los indicadores y la bandeja operativa. | PASS |
| Gerencia | Caja | La ruta mostró “No tenés permiso para ver esta sección”. No se modificaron permisos. | NEEDS-VERIFICATION |
| Recepción | Reserva marcada `QA-OP` (aislamiento no verificado) | Abrió la ficha y sus controles operativos. El resumen financiero mantuvo “No se pudo cargar el resumen financiero”; la API de resumen respondió HTTP 403. No se registró cobro. | FAIL — permiso efectivo por verificar |

## Salud del despliegue

- `GET https://api.hotels-pms.com/health`: estado `ok`, SHA `e36f1d90daf415858fb4a44cdcacdca17d4a750c`.
- `GET https://app.hotels-pms.com/build-meta.json`: mismo SHA.
- `GET https://api.hotels-pms.com/health/ready`: Postgres `connected`; Redis `connected=false`; servicio listo en modo degradado y lock crítico respaldado por advisory lock de PostgreSQL.
- No se usó Render QA ni se consultó la base de datos del proveedor.

## Comprobación adicional de solo lectura

- Gerencia abrió una reserva marcada `QA-OP` desde el Dashboard. El resumen de cobros se mostró con total operativo, pagado, saldo y seña; no se registró ningún cobro ni se completó check-in.
- En esa lectura, el navegador midió **1.704 ms** para el GET del resumen (`HTTP 200`; una muestra) de una reserva marcada `QA-OP`, cuyo aislamiento no está verificado. Es una observación, no un benchmark.
- La pestaña de Gerencia conservaba 49 minutos de `PerformanceResourceTiming`: `/api/reservations/actions/pending` demoró **10.834 s** (n=1), `/api/auth/session/refresh` **8.220 s** (n=1), llegadas **6.208 s** (n=1), ocupación **5.412 s** (n=1), y `/api/reservations/` tuvo mediana **4.794 s** y máximo **4.909 s** (n=3). Las 182 solicitudes de `/api/notifications` en ese período tuvieron p95 **732 ms** y máximo **3.321 s**. Las muestras de Gerencia enumeradas respondieron HTTP 200; el 403 de Recepción figura por separado arriba. Son tiempos de extremo a extremo del navegador y muestras pequeñas para los endpoints individuales; no sustituyen una medición de servidor ni p95/p99 estable.
- La diferencia con Recepción sigue sin quedar explicada por el código del PR #117: el endpoint aplica `cash:operate`, el default de Recepción lo permite y los tests locales esperan HTTP 200. Un override efectivo por hotel o usuario puede negar el permiso; hace falta consultar `GET /api/permissions/effective` desde la misma sesión de Recepción para distinguir configuración de un problema de identidad/runtime. No se cambió ningún permiso.
- Estas mediciones muestran esperas concretas en Dashboard y notificaciones; aún falta correlacionarlas con métricas de pool/DB y estado efectivo de Redis antes de atribuir la causa.

## Validación local del cambio de rendimiento

- Grupo focal de ocho módulos (`analytics_facts`, `reservation_operations_service`, `reservation_service`, `reservation_operations_api`, `reservation_lifecycle_v72`, `reservation_group_service`, `soft_delete` y `v72_change_dates`): **102 aprobadas, 1 xfail y 1 falla**.
- La falla es `test_pending_actions_endpoint_is_hotel_scoped`, que devuelve una lista vacía en lugar de una acción pendiente. Ya se reprodujo sin cambios sobre el SHA base `e36f1d90daf415858fb4a44cdcacdca17d4a750c`; no la introdujo este parche.
- Las pruebas corren con SQLite local y cubren la nueva ruta de borrado lógico, comparaciones del refresh dirigido contra el refresh completo, TTL/FX, eventos de estado, movimiento pagado y aislamiento por hotel. No equivalen a PostgreSQL ni a una medición de latencia de producción.

## Límites y seguimiento

- Entorno: dominio compartido etiquetado como producción; no elegible para gate de release.
- Cobertura: Dueño, Gerencia y Recepción. Codueña, Limpieza y master-admin quedan fuera del alcance confirmado.
- Solo se inspeccionaron pantallas y endpoints de salud. No se midieron tiempos de guardado porque no hay una fixture aislada confirmada para mutaciones financieras o de reservas.
- No se accedió a Gmail, no se enviaron comunicaciones y no se activaron pagos, gastos, webhooks ni OTAs.
- Las observaciones son manuales y redactadas; no hay capturas persistidas. Este registro no certifica el release.
- Riesgo separado: investigar la desconexión de Redis y confirmar si el replay del outbox está activo en el servicio efectivo. No cambiar permisos ni la política de publicación sin verificar esa configuración.

## Addendum — candidata de rendimiento posterior al PR #118 (2026-10-05)

### Cambios y evidencia local

- La bandeja de acciones pendientes ahora agrupa las lecturas por hotel y reserva. En SQLite local, la consulta se mantuvo en **12 consultas** con 5 y con 25 candidatas, frente al fanout previo. La lectura del resumen operativo agrupó historiales OTA, ajustes y movimientos; en el fixture sintético bajó de **62 a 25 consultas**, manteniendo las aserciones de paridad financiera.
- El lote OTA selecciona el enlace más reciente por reserva y hotel (`updated_at`, luego ID), sin cargar todo el historial. La actualización de hechos analíticos incluye la habitación anterior tras un cambio de habitación; el Dashboard reutiliza los hechos cargados y Pickup proyecta solo las columnas y fechas necesarias.
- Redis ahora usa timeouts de conexión/lectura acotados. La publicación de eventos después del commit conserva los escalares requeridos para evitar lecturas SQL accidentales sobre objetos ORM expirados.
- Suite backend completa sobre SQLite local, antes del último ajuste estrecho de lectura OTA: **2.836 pasadas, 34 omitidas y 12 xfail**. Con el ajuste final: grupo focalizado **157 pasadas**. Playwright Chromium local: **164 pasadas y 6 omitidas**; el E2E de roles posterior al ajuste: **18 pasadas**. El E2E completo precedió al último ajuste OTA.
- No se pudo ejecutar la cobertura PostgreSQL local porque el servicio esperado no era alcanzable por el puerto configurado. Los resultados SQLite no sustituyen esa validación.

### Estado en nube y límites

- La comprobación previa a publicar sigue mostrando SHA `ba2243ae5346ddafed58222d9206a1dce7cc1bfe` en `/health` y `/build-meta.json`; por tanto, esta candidata todavía no estaba desplegada en esa comprobación.
- `/health/ready` informó PostgreSQL conectado y Redis desconectado, con la aplicación lista en modo degradado. Render continúa en plan Free; no se usó un servicio Render de QA.
- La navegación en nube se mantiene como observación de solo lectura sobre un dominio compartido. No se registraron cobros, gastos, reservas, permisos, correos ni webhooks; las cuentas observadas no prueban una base aislada. Esta evidencia no certifica un release.
- Las cifras de consultas son fixtures SQLite y las mediciones anteriores de producción fueron muestras de navegador pequeñas. Falta volver a medir solo lectura después del despliegue y comparar el SHA servido; no se atribuye a estos cambios una mejora de latencia de producción hasta contar con esa medición.
- Permanecen sin cambios el recorte temporal y el tope de candidatas de la bandeja de acciones; pueden dejar fuera alertas fuera de esa ventana. La clave de caché del Dashboard sin fechas explícitas puede retener el período previo hasta 60 segundos al cambiar el día local. Son límites existentes, no bloqueantes de esta optimización.
