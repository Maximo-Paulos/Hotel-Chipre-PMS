# Informe final: fallos de simulación, lentitud y consumo

El mapa visual para explicar el sistema a una persona desarrolladora está en [Mapa de arquitectura actual](../architecture/mapa-arquitectura-actual.md).

### Datos de esta revisión

- **Fecha de corte:** 12 de octubre de 2026.
- **Código revisado:** commit funcional `9e4b357c1a0336277c7416751ecb9c08eea4310e` en `fix/lock-paid-room-reservations`.
- **Estado:** no quedan fallos inesperados en las pruebas automatizadas locales. El commit está publicado en el PR #125, que sigue abierto como borrador. Render y Supabase continúan sin verificación de esta versión; también falta la aceptación del hotel y comprobar la configuración activa.

## Resumen para decidir

Se corrigieron localmente los fallos conocidos de las dos semanas simuladas y los mecanismos que repetían consultas o trabajo de más. La batería completa de backend/PostgreSQL, frontend y los recorridos E2E registrados en este informe están aprobados. El backend sigue apagado en Render y esta rama no se desplegó.

**Hay dos problemas comprobados que se mezclaron, pero los datos no prueban que uno solo haya generado todos los GB:**

1. **Render redujo mucho el margen incluido.** El plan Hobby pasó de 100 GB a 5 GB al mes el 1 de agosto de 2026. En el panel revisado aparecían 7,18 GB de tráfico iniciado por servicios y 135 MB de respuestas HTTP. La cuota más chica explica por qué el sistema puede agotarla mucho antes que antes. El ritmo de 7,18 GB en tres días fue reportado por el responsable; multiplicarlo por diez da 71,8 GB en 30 días, pero eso es una proyección, no una medición.
2. **El código desplegado repetía trabajo.** En `e172ceb`, cada stream de actualizaciones podía consultar PostgreSQL cada dos segundos. Además, había pantallas que repetían lecturas cada 10, 15, 30 o 60 segundos. Supabase acumulaba 2,97 millones de ejecuciones del sondeo del outbox desde abril. Esto confirma una amplificación real de consultas y trabajo de base de datos. No dice cuántas ocurrieron durante los tres días del pico ni cuántos bytes generaron.

La conclusión más sólida es que el código contribuía al **exceso de consultas y a la carga de Supabase**, mientras que la reducción de la cuota de Render hizo mucho más fácil superar su límite. **La causa exacta de los 7,18 GB de Render sigue sin estar identificada:** esa categoría representa tráfico iniciado por el servicio hacia destinos externos, pero el panel consultado no muestra los destinos ni el tamaño por ruta. No sería correcto atribuir esos GB al sondeo SQL sin esa evidencia.

La remediación local está lista para el siguiente paso que definiste: reactivar Render para verificar el SHA, la conexión real con Supabase, el cron y el consumo bajo observación. Eso no equivale a declarar cerrado el release ni garantiza capacidad para 400 empleados concurrentes. En una prueba acotada, la API corrió con **0,5 CPU y 512 MiB de memoria, sin swap**: dos recorridos E2E pasaron y el pico fue **301,5 MiB**, sin eventos de presión ni OOM. Falta probar que la conexión real de Supabase admite `LISTEN/NOTIFY` y repetir la aceptación operativa con los cinco roles.

En esta revisión se usaron los paneles de Render y Supabase y consultas `SELECT` de solo lectura en Supabase. El código se publicó en la rama del PR #125; no se mezcló a `main`, no se activó el backend ni se hizo un despliegue de producción. Tampoco hubo cambios de plan o facturación, pagos, correos ni webhooks.

## Lo comprobado sobre Render y Supabase

### Render

- La cuenta está en el workspace **Hobby** y el servicio `hotel-backend` usa el plan de cómputo **Free**. El último SHA de despliegue que muestra el panel es `e172ceb84dba26180f34ef2adad30df5d65ae21c`; no es el código local de esta remediación.
- El panel mostraba **7,32 GB en total**: **7,18 GB de tráfico iniciado por servicios** y **135 MB de respuestas HTTP**. Render define el primer indicador como comunicaciones iniciadas por un servicio hacia destinos externos, por ejemplo bases externas o APIs. No es un contador de consultas ni de solicitudes que llegan desde el navegador. El panel que se revisó no mostraba el destino de esos bytes.
- Render también documenta que un servicio Free puede suspenderse si inicia un volumen inusualmente alto de conexiones externas, por ejemplo a bases de datos o APIs. Es una vía de suspensión posible, separada del límite de ancho de banda; no hay evidencia suficiente para afirmar que esa política causó este caso. La respuesta 503 observada con `x-render-routing: suspend-by-user` indicaba suspensión manual del dueño, así que tampoco prueba una suspensión automática por cuota.
- Render confirma que Hobby bajó de **100 GB a 5 GB** incluidos desde el 1 de agosto de 2026. Esto puede explicar el cambio repentino de cuota aunque el sistema ya viniera funcionando. La cuenta hoy está en Hobby, pero no tenemos una captura de la configuración histórica para certificar desde qué día aplicó a esta cuenta.
- El panel de métricas de CPU y memoria no aporta medición útil mientras el servicio está suspendido.

Fuentes oficiales: [cambio de planes de Render](https://render.com/docs/new-workspace-plans), [tráfico saliente](https://render.com/docs/outbound-bandwidth), [métricas por servicio](https://render.com/docs/service-metrics), [límites de servicios Free](https://render.com/docs/free), [precios](https://render.com/pricing) y [servicios Cron](https://render.com/docs/cronjobs).

### Supabase

- Al revisar la cuenta, el proyecto seguía `Healthy`, con un tamaño aproximado de 63 MB. El aviso era de egreso/cuota, no de caída de la base.
- El panel mostraba **5,976 GB de egreso frente a 5 GB incluidos**, con un aviso de posible restricción del proyecto desde el 5 de noviembre si continúa el exceso. El ciclo mostrado iba del 19 de septiembre al 19 de octubre de 2026.
- El egreso de Supabase mide datos enviados por sus servicios a sus clientes; **no equivale a cantidad de consultas**. Si la app usa el pooler compartido de Supabase, ese tráfico se etiqueta como egreso del pooler compartido. Por separado, `pg_stat_statements` acumula estadísticas desde su último reinicio, el **19 de abril de 2026**. La consulta del outbox del realtime llevaba **2.971.244 ejecuciones**, unos **32 minutos de tiempo de ejecución SQL acumulado** y aproximadamente **1 ms de media**; produjo 29.047 filas en total. La mayoría de los sondeos no encontraba eventos. El promedio acumulado es de alrededor de 17.000 ejecuciones por día durante el período, pero no permite reconstruir el pico de tres días ni los bytes transferidos.
- También hay un indicador de consultas de logs del orden de 294,7 GB a nivel de organización. Es otra métrica del panel y no debe sumarse al egreso de la aplicación ni interpretarse como tráfico PostgreSQL enviado al backend.
- La consulta de rotación de sesiones con bloqueo aparece **473 veces**, con media de unos **708 ms** y máximo de **6,69 s**. No es un volumen comparable al polling del outbox, pero puede explicar parte de la lentitud de recuperación de sesión. La razón de esas esperas históricas no queda identificada por este contador.
- `DROP SCHEMA public CASCADE` aparece **32 veces** en estadísticas acumuladas de producción. El repositorio contenía una prueba de migración con esa instrucción; sin embargo, no hay marca temporal, usuario ni caller suficientes para probar que esa prueba originó las ejecuciones. La base ahora tiene tablas, una revisión de Alembic y datos estimados; eso demuestra que no está vacía hoy, no descarta un incidente histórico. Por el riesgo, la prueba se cerró con una validación explícita de aislamiento, base de datos esperada y entorno local antes de permitir el borrado. La prueba completa pasó contra una base local nueva.

La documentación actual de Supabase aclara que los registros de API Gateway todavía no incluyen bytes de respuesta por ruta. Eso limita la atribución histórica. También distingue conexión directa, pooler de sesión y pooler de transacciones: `LISTEN/NOTIFY` requiere conexión directa o de sesión; el modo de transacciones no conserva ese estado. El código nuevo rechaza el puerto del pooler de transacciones y usa el sondeo limitado si no puede abrir el listener.

Fuentes oficiales: [egreso de Supabase](https://supabase.com/docs/guides/platform/manage-your-usage/egress), [estadísticas de `pg_stat_statements`](https://supabase.com/docs/guides/observability/inspect) y [modos de conexión PostgreSQL y límites de `LISTEN`](https://supabase.com/docs/guides/database/connecting-to-postgres).

### Qué podemos concluir

- **Confirmado:** la cuota Hobby actual es 5 GB; el panel superaba esa cuota; el backend estaba configurado en Free; el panel mostraba 7,18 GB iniciados por servicios y 135 MB de respuestas HTTP; el código desplegado podía consultar el outbox cada dos segundos por stream; Supabase tenía millones de ejecuciones acumuladas y el egreso también excedía su cuota.
- **Confirmado como amplificador de consultas:** el sondeo de 2 segundos y los refrescos periódicos del navegador producían trabajo repetido. Este es un problema real de eficiencia y se corrigió localmente.
- **Probable como explicación del agotamiento rápido:** una cuota diez veces menor dejó mucho menos margen para el volumen de tráfico que la aplicación ya generaba.
- **No demostrado:** qué destino produjo los 7,18 GB iniciados por Render; cuánto de los 5,976 GB de Supabase corresponde a cada ruta o servicio; que el sondeo del outbox generara la mayoría de los bytes; que las 2,97 millones de llamadas ocurrieran en los tres días del pico; que el contador `DROP SCHEMA` provenga de una ejecución de CI o haya borrado datos; o que el patrón de consumo siguiera igual luego de los cambios locales.

### Qué significa cada contador

| Medida | Qué cuenta | Qué demuestra aquí |
| --- | --- | --- |
| Render, respuestas HTTP | Bytes que el backend envía al navegador. | El panel mostró 135 MB; no explica los 7,18 GB de tráfico iniciado por servicios. |
| Render, tráfico iniciado por servicios | Comunicaciones que el backend inicia hacia destinos externos, como bases o APIs. | El panel mostró 7,18 GB, pero no identifica destino ni ruta. |
| Supabase, egreso | Bytes que los servicios de Supabase envían a sus clientes; puede incluir resultados de consultas. | El panel mostró 5,976 GB frente a 5 GB incluidos. |
| `pg_stat_statements` | Número y duración de ejecuciones SQL, junto con filas; no registra bytes por consulta. | Confirma millones de sondeos, no que ellos hayan producido todos los GB. |

Los sondeos desde el navegador llegan a Render como tráfico entrante, que Render no cobra. Las respuestas del backend al navegador aparecen en “respuestas HTTP”. En cambio, una consulta que Render inicia hacia una base puede aparecer como tráfico iniciado por servicios; la respuesta que sale de Supabase puede sumar al egreso de Supabase. Son medidas relacionadas, pero no se pueden equiparar ni usar una para atribuir automáticamente la otra.

## Fallas de código que podían amplificar la carga

| Mecanismo encontrado | Efecto | Corrección local |
| --- | --- | --- |
| Recuperación HTTP del stream | Cada pestaña podía consultar recuperación cada cinco segundos cuando realtime se degradaba. | El intervalo se amplía a 60 segundos; fallos transitorios usan espera creciente hasta cinco minutos. No se repiten errores de autorización. |
| Consulta SQL por stream | El despliegue consultaba PostgreSQL cada dos segundos por cada stream abierto. | El camino normal usa `LISTEN/NOTIFY` compartido por proceso. Si cae, el respaldo se limita a una consulta cada 60 segundos por hotel/proceso. Falta probar el modo de conexión real de Supabase. |
| Refrescos automáticos del navegador | El código desplegado refrescaba WhatsApp cada 15 s; notificaciones, Gemma y enlaces de pago cada 30 s; conflictos de habitación cada 60 s; y pruebas de configuración cada 10 s cuando esas pantallas estaban activas. | Se quitaron esos intervalos de las pantallas revisadas; la carga ocurre al abrir o por cambio relevante. La prueba de reposo no vio consultas posteriores ni reconexiones SSE durante 65 segundos. |
| Lista de acciones pendientes (N-02) | Una lectura llegó a ejecutar 525 consultas para 38 reservas por repetir el resumen de cada reserva. | Las lecturas se agruparon y los totales se calculan en SQL. |
| Reintentos de lectura | Un error del backend podía provocar hasta cuatro solicitudes contando el primer intento. | Se deja un solo reintento transitorio; 4xx no se repiten. |
| Analytics con escritura dentro de GET | Leer podía reconstruir hechos de hasta 31 días y escribir en PostgreSQL. | La lectura ahora es de solo lectura; la reconstrucción está fuera del GET. |
| Trabajos al iniciar sesión | Cada login podía disparar tareas para todos los hoteles. | Se quitaron del login y se ejecutan con trabajo programado limitado por hotel. |
| Optimizador al crear reserva | El alta podía volver a optimizar aun si ya había asignado habitación. | Una reserva asignada no vuelve a iniciar la optimización global. Los casos dudosos requieren revisión manual. |
| Optimizador con trabajo redundante | Comparaba reservas sin fechas superpuestas y usaba cuatro trabajadores. | Solo evalúa pares que pueden superponerse y usa un trabajador. |
| Informe de saldos | El costo crecía al comparar reservas, pagos y ajustes repetidamente. | Total global exacto en SQL y detalle paginado. |
| Avisos del reporte diario | La consulta de avisos agrupaba todos los pagos y ajustes del hotel, aunque esos importes se recalculaban después solo para las reservas seleccionadas. | La consulta de avisos ahora trae únicamente los datos necesarios; las consultas financieras se reservan para los totales globales y la página visible. |
| Respuestas e invalidaciones grandes | Algunas pantallas solicitaban más datos o actualizaban listas ajenas a la acción. | Se redujeron detalles e invalidaciones y se agregó compresión HTTP. |

Son amplificadores de consultas comprobados en código y/o pruebas. Explican lentitud y carga de base mejor que el volumen de bytes de Render. Ninguna permite repartir el egreso histórico entre rutas o destinos.

### Cuánto podía repetirse el sondeo realtime

Un sondeo cada dos segundos equivale a **30 consultas por minuto y 43.200 por día por cada stream que permanezca abierto**. Ocho streams abiertos todo el día equivaldrían a 345.600 sondeos diarios; es una cuenta teórica desde la frecuencia del código, no el tráfico observado en producción. En el código actual, el camino normal recibe avisos con `LISTEN/NOTIFY` mediante un listener compartido. Si el listener falla, se limita el sondeo a una vez por minuto por hotel y proceso: hasta 1.440 consultas diarias por hotel con actividad continua. La comprobación de membresía sigue ocurriendo cada 60 segundos por stream para cerrar el acceso cuando se revocan permisos; es un control de seguridad, no una recarga de datos de la pantalla.

## Cambios aplicados

### Áreas del sistema modificadas

- **Backend FastAPI y PostgreSQL:** autenticación y recuperación de sesión; reservas, pagos, tarifas y restricciones; permisos; reportes y Analytics; configuración por hotel; eventos realtime; cierres de conexiones; trabajos programados y no-show.
- **Frontend React:** política de reintentos, actualización selectiva de datos, carga diferida de consultas, estados de permisos, formularios de reservas, reportes, caja, lavandería y configuración de impuestos.
- **Persistencia y operación:** migraciones para eventos y políticas por hotel; compresión HTTP; perfil local PostgreSQL; cron SQL-only cada cinco minutos; Redis y NoSQL permanecen fuera de la ruta.
- **Regresiones:** cobertura backend, PostgreSQL y Chromium para permisos, pagos, consultas, políticas, realtime y actividad en reposo. La prueba destructiva de migraciones ahora exige URL y evidencia de una base local aislada, y confirma el nombre de la base conectada antes de borrar. También fija `APP_ENV=test` al ejecutar Alembic. Se corrigió además el fixture de movilidad: el caso no creaba una habitación accesible aunque esperaba que la reserva se asignara; ahora la prueba verifica la regla con datos válidos.

### Menos consultas y menos datos

- El cliente dejó de sondear periódicamente las áreas revisadas. Después de una modificación solo actualiza las listas relacionadas con esa modificación.
- El respaldo realtime no consulta en paralelo mientras el stream está conectando o reintentando; cuando queda degradado, espera 60 segundos y aumenta la pausa si la recuperación falla.
- Guardar caja confirma la escritura sin esperar a que terminen las recargas secundarias.
- Las consultas de creación y de incorporación de huéspedes se agruparon para evitar lecturas repetidas.
- Los saldos conservan el total global exacto, pero devuelven el detalle por páginas.
- Las respuestas HTTP grandes usan compresión gzip.
- El backend ahora deja datos para la próxima ventana activa: tiempo y consultas SQL por ruta, espera del pool, destino PostgreSQL, tamaño estimado de las consultas SQL, bytes de respuesta HTTP comprimida y host/tamaño estimado de llamadas HTTP a otros servicios. No mide los bytes exactos de las respuestas PostgreSQL por ruta, así que no reconstruye el egreso histórico de Supabase ni reemplaza el panel de Render.
- El frontend ya es React con TanStack Query. El arreglo se hizo en cuándo consulta y qué datos invalida; no hacía falta cambiar de framework.
- La caché sigue desactivada en el perfil SQL-only. PostgreSQL permanece como fuente de verdad; no se agregó Redis ni NoSQL.

### Realtime y trabajos programados

- Las notificaciones internas se guardan en el outbox de PostgreSQL y se publican con LISTEN/NOTIFY.
- Si el listener no está disponible, el respaldo consulta como máximo una vez cada 60 segundos por hotel y proceso, no cada dos segundos por stream.
- El listener PostgreSQL es una conexión compartida por proceso; cada stream cierra la conexión inicial de autenticación y no la conserva mientras queda abierto.
- Para habilitarlo, Render debe recibir una conexión directa o de pooler de sesión de Supabase en el puerto 5432. El pooler de transacciones (6543) no conserva `LISTEN`; el código detecta ese puerto y usa el respaldo acotado. Aún falta verificar la conexión real configurada en Render.
- Cada stream vuelve a comprobar que el usuario conserve su cuenta y membresía cada 60 segundos. Es un control de seguridad para limitar el acceso después de revocar permisos; no es un sondeo HTTP del navegador.
- Los trabajos de avisos y no-show dejaron de ejecutarse por login. El runner procesa los hoteles de forma acotada y el cron versionado se programa cada cinco minutos.
- El cron no está provisionado ni probado en Render. El código y la prueba local no demuestran que el servicio exista en la cuenta activa.

### Reglas funcionales confirmadas por el responsable

- Una reserva con habitación y pago asignados no se mueve automáticamente. Requiere revisión manual.
- Una reserva confirmada no cambia de tarifa desde el flujo normal; el caso se revisa manualmente.
- Un huésped restringido no recibe una excepción automática; el operador revisa el caso.
- Cada hotel debe configurar impuestos, depósitos y reglas de lavandería antes de operar esos flujos.
- Los reclamos por ropa blanca faltante quedan sin monto.
- Se mantienen los permisos existentes y cada aviso llega solo a quienes tienen permiso para esa área.
- Los trabajos programados respetan el alcance de cada hotel.

### Fallos de las simulaciones

En semana 1 se trabajaron reservas, habitaciones, pagos, caja y cierres, permisos y sesiones, onboarding, grupos, tarifas, restricciones de huéspedes, reportes, lavandería, inventario y mensajes en español. La sección de pendientes de este informe concentra los puntos que aún requieren una decisión o verificación; los demás recorridos tienen corrección local y la evidencia automatizada resumida más abajo.

Para semana 2 se integraron los arreglos conocidos de concurrencia en pagos y PostgreSQL, permisos y recuperación de sesión, conexiones, no-show, tarifas y extensiones, exportaciones e informes, reembolsos, lavandería, recibos, mensajes y validaciones, huéspedes restringidos y confirmaciones.

Esto describe el estado del código y las pruebas locales. **La simulación automatizada no reemplaza la repetición con Dueño, Codueña, Gerencia, Recepción y Limpieza usando el flujo real.**

### Ronda 2: fallos críticos y tratamiento local

La simulación semanal original encontró 16 de 31 recorridos funcionando, 10 a medias y 5 sin cambio. Esa fotografía es anterior a los arreglos locales de esta rama. Los hallazgos más importantes quedaron así:

| Hallazgo | Qué fallaba | Corrección local y estado |
| --- | --- | --- |
| N-01 — cobros en PostgreSQL | El bloqueo de una reserva con relaciones podía devolver HTTP 500 y frenar pagos. | El bloqueo SQL se limita a la tabla correcta. Se cubre con pruebas PostgreSQL; la suite final vuelve a ejecutar ese camino. |
| N-02 — lista de acciones | Una sola lectura llegó a ejecutar 525 consultas para 38 reservas. | Se agruparon las lecturas y sumas por página. El total operativo incorpora ajustes de manera consistente con la ficha, sin mezclar hoteles ni reservas de cuenta corriente. |
| N-03 — sesión | Una lectura demorada podía expirar mientras el backend rotaba el token de sesión. | La recuperación de una rotación interrumpida se amplió y se reintenta de forma acotada; se agregaron regresiones de sesión. El motivo exacto de cada logout histórico no se puede reconstruir sin los registros de producción. |
| N-04 — invitaciones | Dos lecturas de invitaciones pedían permiso de escritura/2FA y la pantalla quedaba cargando. | Las lecturas usan permiso de consulta y la interfaz presenta un único pedido de 2FA cuando realmente hace falta. |
| N-05 / R23 — reservas vencidas | Reservas vencidas, incluso pagadas, quedaban sin estado final. | Se añadió un proceso SQL por hotel cada cinco minutos, con controles de idempotencia. Falta crear y verificar el Cron en Render. |
| N-06 a N-08 — mensajes y validaciones | Algunos errores salían en inglés, se mostraban claves técnicas o los botones no explicaban qué dato faltaba. | Se localizaron mensajes y permisos, y se añadieron errores visibles para datos incompletos y confirmaciones de tarifas. |
| N-09 / R17 — lavandería | La vuelta parcial de ropa fallaba y no distinguía unidades faltantes. | El flujo permite registrar cantidades y seguimiento por hotel; el reclamo al proveedor queda sin monto por decisión del responsable y no crea cargos/pagos. |
| N-10 / R13 — permisos | No había evidencia clara de cambios individuales. | El guardado de permisos individuales ahora tiene regresión de interfaz, persistencia y auditoría. |
| N-11 / R31 — saturación y stream | Consultas repetidas y una conexión SSE no liberada podían consumir conexiones e hilos. | Se limitó el trabajo concurrente, se añadió respuesta 503 al agotarse el pool y se corrigió la limpieza del stream. El listener PostgreSQL local se comparte por proceso. |
| F-074 / R28 — total de reserva | La lista y la ficha podían mostrar distintos importes operativos. | La lista suma ajustes en SQL para las reservas de la página y mantiene el filtro por hotel y moneda. |

Los estados iniciales R01–R31 cambiaron durante esta remediación, así que esa clasificación histórica ya no describe el checkout actual. Aquí se presenta el estado vigente: cambios locales y mediciones, seguidos por los pendientes de configuración, aceptación humana o servicios externos.

## Mediciones locales

Las siguientes mediciones se hicieron con datos sintéticos en PostgreSQL 16 local. No contienen datos de producción.

### Reporte diario: menos trabajo para armar los avisos

Encontré que la consulta de avisos hacía dos agregaciones globales: recorría y agrupaba todos los pagos y ajustes del hotel. Esos valores no se usaban en la pantalla de avisos: el servicio volvía a obtener los importes, esta vez para los IDs seleccionados. Quité el cálculo duplicado; los avisos y la información financiera siguen cubiertos por las mismas reglas.

La comparación se hizo en una base local desechable con 2.000 reservas, **40.667 pagos y 40.000 ajustes sintéticos** distribuidos dentro de un hotel. La base PostgreSQL tuvo un límite de 0,5 CPU y 512 MiB de RAM, más hasta 512 MiB de swap. Con 46 avisos elegibles, el costo de esa consulta pasó de **12,07 ms a 2,87 ms** y sus lecturas de buffers bajaron de **1.036 a 214**. El reporte completo bajó de **67,03 ms a 54,64 ms de mediana** y de **90,43 ms a 73,13 ms en p95**. Siguió usando 12 sentencias SQL; el ahorro está dentro de una de ellas. Las pruebas conservaron los mismos avisos, orden, alcance por hotel y saldos.

Esta mejora reduce trabajo de PostgreSQL. **No explica el egreso de Render:** esas agregaciones ocurrían dentro de la base y la consulta entregaba las mismas filas al backend. El sondeo repetido del outbox explica una parte demostrable de la carga de consultas; los bytes históricos de Render siguen sin una causa atribuible por ruta.

### Consultas de saldos con 2.000 reservas

| Medición | Tiempo | Lecturas de buffers |
| --- | ---: | ---: |
| Cálculo anterior, con comparaciones repetidas | 10.558 ms | 16.272.070 |
| Proyección corregida | 15,79 ms | 30.006 |
| Total global exacto en SQL | 5,49 ms | 16.066 |
| Página de 50 detalles | 0,38 ms | 701 |

La página trae hasta 50 detalles y el total sigue incluyendo todas las reservas que tienen saldo. Estos son tiempos de consulta, no el tiempo completo de la respuesta en producción.

### Optimizador de habitaciones

Con 391 reservas sintéticas y 40 habitaciones:

| Configuración | Tiempo total | Pico RSS |
| --- | ---: | ---: |
| Cuatro trabajadores | 2.396 ms | 539,1 MiB |
| Un trabajador | 2.386 ms | 405,6 MiB |

La memoria medida del proceso del solver bajó alrededor de un 25% sin empeorar el tiempo de esa ejecución. Se agregaron regresiones para que no vuelva a usar cuatro trabajadores.

### Perfiles locales de varios hoteles

Ya se había probado el perfil de presupuesto de una API con **50 hoteles y 400 identidades** (ocho personas por hotel), PostgreSQL local y límite de **512 MiB** para el backend: completó **900 solicitudes en 59,9 segundos**, sin errores ni reinicio, y el uso máximo del proceso fue **356,9 MiB**. En una ráfaga aparte de 100 lecturas simultáneas, las 100 respuestas fueron HTTP 200, pero la cola de admisión llegó a aproximadamente **502 ms**. Esto es evidencia sintética útil para el límite de memoria; no equivale a 400 empleados operando simultáneamente ni a una garantía del proveedor.

También se midieron **300 flujos concurrentes de cotización y alta**, distribuidos entre 50 hoteles: terminaron 300/300 cotizaciones y 300/300 altas sin errores. El ciclo completo tuvo p95 de **4,18 segundos**; la cola de admisión explicó la mayor parte de la espera y cada alta todavía ejecutó hasta **37 consultas SQL** en una muestra aislada. La consulta de base local tardó decenas de milisegundos, pero una conexión remota agrega viajes de red. Por eso este perfil muestra que la aplicación puede completar una ráfaga sintética, a la vez que identifica una oportunidad pendiente para reducir viajes SQL y espera bajo concurrencia.

Estos dos perfiles se conservaron de mediciones anteriores para no repetir cargas idénticas. El ensayo de 30 minutos que sigue corresponde al código local actual y se registrará aparte.

### Pruebas funcionales y de consumo

- Backend: la repetición completa terminó con **3.113 aprobadas, 17 omitidas y 12 fallos esperados**, sin fallos inesperados, en **6 minutos y 22 segundos**. Se ejecutó con SQLite en memoria para los casos comunes y PostgreSQL 16 local aislado para los flujos de base que requieren PostgreSQL. Hubo 59 advertencias de dependencias/ORM, sin fallos de pruebas.
- Frontend: **128 pruebas aprobadas**, con lint, chequeo de tipos y compilación correctos. El paquete JavaScript principal de Vite sigue mostrando una advertencia de tamaño: **571,31 kB sin comprimir (179,23 kB gzip)**.
- Chromium sobre PostgreSQL 16 local: la matriz amplia registró **185 aprobadas, 6 omitidas y 0 fallidas** en 11,3 minutos. Los seis casos omitidos son pruebas especiales habilitadas por separado: una invitación real de Google, una configuración específica de impuestos, el ensayo F-003 de 30 minutos y tres pruebas de carga H31. Después de corregir el autoarreglo de esquema al iniciar, los recorridos de guardado de reserva y reposo se repitieron y pasaron **2/2**; el worker procesó **1 de 1** trabajo dentro del hotel con RLS activo. Los otros recorridos focalizados de impuestos, eventos realtime entre sesiones y cierre de caja también pasaron. En esta continuación no repetí la matriz Chromium porque las modificaciones posteriores fueron únicamente al harness de pruebas backend; no cambiaron la aplicación ni el frontend.
- Los tres tests H31 se ejecutaron aparte con el hotel sintético de 30 habitaciones. La vista de habitaciones pasó en las cuatro sesiones; los otros dos casos pasaron tras corregir una expectativa de test que pedía el texto “Libre” aunque una habitación bloqueada muestra “libre desde”. Resultado de la repetición: **3/3 pasaron**.
- Migraciones PostgreSQL: **1/1 aprobada** en una base PostgreSQL 16 local recién creada; comprobó instalación nueva, repetición idempotente, retroceso de una revisión y avance otra vez al head.
- La primera repetición del backend había mostrado 11 fallos de pruebas. Se corrigieron cuatro problemas de configuración/expectativa del harness: habilitar explícitamente la compuerta para el login Google simulado; ejecutar la comprobación RLS con un rol sin privilegios de superusuario; comprobar el error de dominio esperado cuando el bloqueo busca una reserva inexistente; y aislar la prueba de seguridad de las variables de entorno del proceso. Luego pasaron la suite completa y los casos PostgreSQL focalizados. El control de documentación pasó **2/2** y `git diff --check` no encontró errores de formato.
- El ensayo F-003 de **30 minutos** sobre el código local actual terminó **1/1 aprobado**: cuatro roles, **825 acciones**, **793 solicitudes API** (0,96 por acción en promedio), **31 reservas nuevas**, p95 de acción **411 ms**, máximo de acción **874 ms**, y creación más lenta de **2.058 ms**. Hubo **cero respuestas 5xx**, cero lecturas prohibidas y cero redirecciones al login. Las 284 aperturas de pantalla consultaron las categorías como máximo una vez. El máximo de solicitudes observado en una acción individual fue 11 al entrar a Reportes; el promedio de esa navegación fue 0,9 porque las vistas reutilizaron datos en las visitas siguientes. En el ensayo hubo 43 lecturas de reservas y 43 de acciones pendientes durante 31 altas, compartidas entre las sesiones autorizadas que debían actualizarse. Es un resultado de un hotel sintético y cuatro roles, no una prueba de 400 usuarios simultáneos.
- La medición H31 abrió cuatro sesiones simultáneas y recargó seis veces la vista con 30 habitaciones: mediana **431 ms**, máximo **901 ms** y **cero respuestas 5xx**. En ese escenario local, las lecturas de habitaciones y reservas respondieron en general en menos de 0,4 segundos; el endpoint más lento registrado fue acciones pendientes, 400 ms.
- La prueba de reposo observó el Dashboard durante **65 segundos** después de estabilizar sus lecturas iniciales: cero requests API adicionales desde el navegador y cero reconexiones SSE.
- Un registro de una prueba E2E anterior informó **512 MiB de pico y unos 479 MiB al finalizar**, pero no se conservaron los datos originales del cgroup y no se pudo confirmar su SHA. Por eso no se mezcló con la prueba actual.
- En esta continuación se repitió el benchmark de PostgreSQL con el contenedor de base limitado a **0,5 CPU, 512 MiB de memoria y hasta 512 MiB de swap**. La API/benchmark corrió en el host local, sin límite de memoria equivalente. El perfil midió 20 iteraciones por operación: alta explícita **12,09 ms p50 / 12,91 ms p95, 18 consultas**; alta con precio automático **13,65 / 17,18 ms, 21 consultas**; disponibilidad **2,28 / 2,42 ms, 3 consultas**; búsqueda de habitaciones **2,82 / 2,90 ms, 4 consultas**; asignación **7,45 / 8,24 ms, 6 consultas**; saldo **7,98 / 11,17 ms, 9 consultas**; reporte diario **41,07 / 68,29 ms, 12 consultas**; búsqueda de huésped por documento **21,91 / 25,69 ms, 8 consultas** y por apellido **24,91 / 28,41 ms, 8 consultas**. Es una medición sintética de PostgreSQL local, no una prueba de latencia ni consumo en Supabase/Render.
- La API de esta rama también se compiló y ejecutó en un contenedor aislado con **0,5 CPU y 512 MiB, sin swap**, conectado a PostgreSQL 16 local. Los E2E de reposo y guardado de reserva pasaron **2/2**. El cgroup registró **315.580.416 bytes actuales y 316.137.472 bytes de pico (301,5 MiB)**; `memory.events` registró cero `high`, `max`, `oom` y `oom_kill`, y los logs no mostraron respuestas HTTP 5xx. Este perfil cubre un hotel de prueba y esos dos recorridos, no una carga de 50 hoteles o 400 sesiones simultáneas.
- Se corrigió también el autoarreglo local de esquema: ahora solo intenta completar columnas que existen y permiten nulos, y no enlaza expresiones SQL de fecha como si fueran valores Python. Las pruebas focalizadas de arranque y configuración del pool pasaron **12/12**; los E2E repetidos ya no muestran esos errores de fecha. El arranque administrado de producción usa migraciones de Alembic y no pasa por esta rutina de reparación; por tanto, este defecto local **no demuestra** la causa del incidente histórico de Render.
- El contenedor PostgreSQL también tuvo límite de 0,5 CPU y 512 MiB de memoria; el sistema local permitía hasta 512 MiB adicionales de swap para PostgreSQL. El API no tenía swap. Esta configuración local no reproduce todos los detalles de los proveedores.
- Graphify se regeneró explícitamente después de los cambios: **14.202 nodos, 48.407 relaciones, 768 comunidades y 1.116 flujos**. `portable-check` pasó con 357 artefactos. Tres archivos Swift no se pudieron leer porque la herramienta instalada no tiene esa gramática. `check-update` todavía indica que faltan etiquetas y descripciones semánticas; no se generaron con IA, según las reglas del proyecto.

La matriz Chromium verificó muchos recorridos de reserva, permisos, caja, pagos, lavandería, reportes y onboarding. La prueba H31 solo representa cuatro sesiones y un hotel; **no certifica capacidad para 50 hoteles y 400 empleados**. Tampoco permite convertir estos resultados en una estimación de GB ahorrados al mes.

## Semana 1: pendientes que siguen abiertos

La mayoría de los hallazgos F-001 a F-053 tiene una corrección local y una prueba asociada. Algunos siguen sujetos a configuración del hotel, revisión legal o aceptación humana; están detallados aquí:

- **F-003:** el soak local actual duró 30 minutos y aprobó con 31 reservas nuevas, 0,96 requests por acción, creación máxima de 2,058 segundos y cero 5xx. El perfil previo con 50 hoteles/400 identidades completó 900 solicitudes bajo 512 MiB; la ráfaga de 100 lecturas mostró unos 502 ms de espera de admisión. Todavía faltan 400 usuarios simultáneos, varios procesos/instancias y la conexión real a Supabase.
- **F-005:** la política para reservas OTA está definida; falta repetir el flujo con el personal del hotel.
- **F-013:** antes de fijar campos obligatorios de documentos o declarar requisitos legales, hay que confirmar la jurisdicción y contrastar la regla aplicable.
- **F-015:** los límites y permisos para ajustar tarifas tienen pruebas locales. El hotel todavía debe definir y cargar el rango real. En reservas confirmadas no se cambia la tarifa automáticamente; el caso queda para revisión manual.
- **F-022:** inventario y traspasos tienen validación local. El hotel debe definir por hotel los precios, impuestos y reglas de cuándo cargar consumos al folio antes de habilitar esas operaciones.
- **F-029:** faltan definiciones del hotel para ADR, ingreso devengado, saldo por cobrar y qué significa el reporte multimoneda cuando no hay reservas.
- **F-026 / H31:** las opciones para definir mínimos por ubicación y los avisos de stock están implementados y probados localmente. El hotel debe cargar sus mínimos y validar los estados reales antes de operar con esos avisos; no se inventaron umbrales.
- **F-046:** minibar se dejó expresamente para una etapa futura: no se agrega catálogo de venta, precio ni cargo al folio en este lote.
- **F-031:** no se autenticó contra Google OAuth real; las pruebas usan cuentas sintéticas.
- Los documentos obligatorios y otras reglas legales quedan sujetos a confirmar la jurisdicción del hotel; no se inventaron requisitos.

## Semana 2: pendientes que siguen abiertos

Los cambios y las pruebas locales están integrados en este checkout, pero no equivalen a la aceptación de los empleados:

- Ejecutar la re-simulación funcional completa con los cinco roles y corregir cualquier diferencia visible que quede.
- Probar los permisos y restricciones con usuarios del hotel y recorrer pagos, reembolsos, caja, recibos, lavandería y reportes en la interfaz.
- Completar la configuración de impuestos, depósitos, mínimos y reglas de lavandería de cada hotel antes de habilitar las operaciones que dependen de esos valores. Si un hotel no cobra impuestos, debe registrar explícitamente una política de 0%; no se asume ese valor por ausencia de configuración.
- Provisionar el cron y verificar que corra una vez cada cinco minutos con alcance por hotel.
- Se considera confirmada una reserva que tiene habitación y pago asignados. No moverla ni cambiarle la tarifa automáticamente. Las excepciones, conflictos de habitación y casos de huésped restringido requieren revisión manual; el permiso de un gerente no produce una excepción automática.
- Mantener los permisos actuales por área; los avisos operativos se envían solo a quienes tienen permiso para esa área.
- Los reclamos a proveedores de ropa blanca quedan sin monto por ahora y no generan cobros, pagos ni movimientos financieros.
- **R14:** la factura electrónica de ARCA no forma parte de esta corrección; antes de integrarla hay que confirmar alcance legal, credenciales y contrato de API.
- **R29:** se registraron los planes de USD 20, USD 100 y USD 200, pero el checkout sigue sin cobrar. La suscripción y la facturación real no se probaron.
- No se probó la entrega real de correo ni la autenticación con OAuth de Google; esas integraciones requieren cuentas y servicios reales.
- La matriz automatizada local pasó, pero todavía falta la aceptación operativa de los cinco roles del hotel.
- El PR #125 sigue en borrador. Después de actualizarlo con el commit funcional `9e4b357c`, GitHub informó temporalmente `mergeable: UNKNOWN`; falta revisar la conclusión de CI en la cabeza final. La vista previa de Supabase figura omitida. No se habilitó ningún gate para evitar QA.

## Límite de gasto de Render

El nuevo plan Hobby incluye 5 GB de salida al mes y cobra el exceso por GB. Pro incluye 25 GB, pero cuesta USD 25 mensuales solo por el workspace; el cómputo de los servicios se suma aparte. El plan Pro por sí solo ya consume todo el presupuesto máximo acordado, así que no es la opción dentro del límite de USD 25. Render documenta también un mínimo de USD 1 al mes para un servicio Cron.

El perfil más económico que respeta la decisión de SQL-only es Hobby, una API Starter de 0,5 CPU/512 MB y un Cron. Con los precios publicados, el punto de partida es aproximadamente **USD 8 al mes** (USD 7 de API y mínimo de USD 1 del Cron), más el cómputo efectivo del Cron y el egreso que supere los 5 GB. Si el ritmo histórico de 7,18 GB cada tres días se repitiera durante un mes, serían unos 71,8 GB: 66,8 GB por encima de la cuota, aproximadamente **USD 10,02 de egreso adicional** a USD 0,15/GB. En ese supuesto, el total partiría de unos **USD 18,02**, antes de cualquier costo adicional del Cron u otros servicios.

Ese cálculo es una estimación, **no un límite de gasto**. Render cobra el exceso de ancho de banda cuando hay un medio de pago asociado; la documentación describe un tope mensual para minutos de compilación, no un tope duro para el egreso. Sin medio de pago, Render puede apagar los servicios cuando se consume la cuota. Por eso no se puede garantizar desde el plan que la factura nunca supere USD 25 si el tráfico crece; hay que revisar el consumo por servicio y destino desde el primer día activo.

Render Hobby y Pro, el tráfico incluido y el costo del exceso están en [precios de Render](https://render.com/pricing) y [medición de ancho de banda saliente](https://render.com/docs/outbound-bandwidth). La [FAQ de Render](https://render.com/docs/faq) explica cuándo se factura el exceso y que el tope configurable documentado corresponde a minutos de compilación, no a ancho de banda. El mínimo de Cron está en [documentación de Cron](https://render.com/docs/cronjobs). Supabase mide egreso en bytes transferidos; el plan Free publica cuota de 5 GB por egreso no cacheado y 5 GB por egreso cacheado, y Pro 250 GB para cada categoría: [uso de egreso de Supabase](https://supabase.com/docs/guides/platform/manage-your-usage/egress).

Al 12 de octubre se confirmó en los paneles que Render está en Hobby con `hotel-backend` Free suspendido, y que Supabase está en Free. No se cambió ningún plan ni se encendió el backend. Estos valores pueden cambiar y deben reconfirmarse justo antes de reactivar; el costo efectivo del cron y el egreso mensual corregido todavía no se pueden medir con el servicio apagado.

## Qué falta para recomendar una reactivación

1. Ya se midió la API actual en el límite de 512 MiB con dos E2E: pico 301,5 MiB y cero eventos OOM. Para certificar crecimiento aún falta repetirlo con varios hoteles, más sesiones simultáneas y operaciones de optimización bajo carga.
2. Correr una prueba progresiva de lecturas y escrituras con varios hoteles y usuarios, midiendo latencia p50/p95, CPU, memoria, conexiones, consultas por pantalla y volumen de respuesta.
3. Instrumentar el siguiente período de observación para comparar solicitudes, bytes por ruta y egreso hacia Supabase; el incidente anterior no dejó esa atribución.
4. Repetir manualmente los escenarios de las semanas 1 y 2 con los cinco roles y cerrar los pendientes funcionales y de negocio enumerados arriba.
5. Antes de reactivar, volver a confirmar los planes, estimar el gasto total con el Cron y fijar una supervisión diaria del egreso; no hay un límite duro de ancho de banda que garantice el techo de USD 25.
6. Cuando el responsable reactive el servicio, verificar /health, /build-meta.json, SHA desplegado, conexión PostgreSQL, listener, cron, egress y recorridos autorizados. Hasta entonces, producción sigue sin verificar.

## Estado y fuentes

- `code_sha` funcional: `9e4b357c1a0336277c7416751ecb9c08eea4310e`, rama `fix/lock-paid-room-reservations`, publicada también como cabeza de [PR #125](https://github.com/Maximo-Paulos/Hotel-Chipre-PMS/pull/125). El PR permanece abierto en borrador y no está integrado en `main`.
- La rama incorpora `origin/main` hasta `b5cc58c0cb7dbef417f8076b881ceba4436afd51`; `main` no se modificó en esta entrega.
- Los reportes y pruebas locales no prueban que el código esté desplegado ni que Render o Supabase estén saludables.
