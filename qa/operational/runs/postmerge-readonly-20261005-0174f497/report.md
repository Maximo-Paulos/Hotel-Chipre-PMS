# QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE

## Resumen

Corrida manual de solo lectura sobre la aplicación compartida posterior al merge del PR #117 y los commits siguientes de `main`. La versión observada es `0174f497cc615550c21ba5c78bac0b6893729c7b`. No se usó Render QA y no se modificaron datos del hotel.

El Dueño pudo abrir Dashboard, Reservas, Caja y Reportes. Caja terminó de cargar sin reproducir el HTTP 422 registrado en una corrida anterior. Reportes mostró temporalmente “Cargando reporte…” y luego presentó sus secciones. Recepción vio la lista de 39 habitaciones. La sesión de Gerencia se dejó intacta porque conservaba un formulario de cobro sin enviar; no se confirmó que esa pestaña ejecutara los assets actuales.

Render muestra el servicio `hotel-backend` en plan Free y advierte que una instancia inactiva puede tardar 50 segundos o más en responder al reactivarse. La preparación actual informa PostgreSQL conectado y Redis desconectado. Las solicitudes HTTP directas dieron entre 274 y 758 ms en muestras pequeñas; no son un benchmark de carga ni miden una operación autenticada.

## Identidad y estado del servicio

- `GET https://api.hotels-pms.com/health`: HTTP 200, `status=ok`, SHA `0174f497cc615550c21ba5c78bac0b6893729c7b`.
- `GET https://app.hotels-pms.com/build-meta.json`: HTTP 200, mismo SHA.
- `GET https://api.hotels-pms.com/health/ready`: HTTP 200, `ready=true`; PostgreSQL conectado; Redis desconectado; `optional_degraded=true`; el lock crítico usa advisory lock de PostgreSQL y figura seguro.
- Muestras directas, sin caché: `/health` 321 ms y 274 ms; `/health/ready` 758 ms y 325 ms; `/build-meta.json` del frontend 205 ms. Son una o dos muestras, sin percentiles.
- En Render se observó la rama `main`, el último despliegue exitoso en el SHA `0174f49` y el plan Free. La interfaz advierte explícitamente una demora de 50 s o más tras spin-down.

## Recorrido visible

| Cuenta | Pantalla | Observación | Estado |
|---|---|---|---|
| Dueño | Dashboard | Se cargaron indicadores, próximas reservas y bandeja operativa; sin error genérico visible. | PASS, solo lectura |
| Dueño | Reservas | Abrió la lista. “Cargando grupos…” desapareció en la siguiente comprobación; no quedó error visible. | PASS, con carga transitoria |
| Dueño | Caja | Secciones de caja, turnos y gastos visibles; sin estado de carga ni error al terminar. No se registró ningún movimiento. | PASS, solo lectura |
| Dueño | Reportes | La primera vista mostró “Cargando reporte…”; una observación posterior mostró el resumen y las secciones del reporte, sin error genérico. No se midió el tiempo total. | PASS, con demora no cuantificada |
| Recepción | Habitaciones | Lista de 39 habitaciones visible; identidad del rol confirmada; no se cambió ningún control. | PASS, solo lectura |
| Gerencia | Pestaña existente | Se conservó sin navegar ni recargar porque tenía un formulario de cobro sin enviar. No queda revalidada contra los assets actuales. | BLOCKED |

Codueña, Limpieza y master-admin quedan fuera por la decisión del usuario de limitar esta pasada a las cuentas abiertas de Dueño, Gerencia y Recepción.

## Auditoría paralela de rendimiento y datos

Dos agentes especialistas revisaron el checkout limpio `0174f497` en modo solo lectura. Sus cifras de consultas provienen de pruebas existentes con SQLite sintético, no de mediciones nuevas ni de PostgreSQL de producción:

- Acciones pendientes: 12 consultas con 5 y con 25 candidatas.
- Listado: máximo 10 consultas para 50 reservas de 120 existentes.
- Grilla: máximo 8 consultas para 38 habitaciones.
- Reporte de ocupación: máximo 3 consultas para 7 días.
- Resumen operativo: fixture local registró 62 consultas antes y 25 después.

Candidato para la latencia de guardado: el hook síncrono `after_commit` intenta publicar en Redis cada evento durable del mismo cambio, uno por uno. Redis está desconectado en producción; eventos de una reserva pueden invalidar varios dominios. Los eventos durables ya están en PostgreSQL y el flujo SSE tiene fallback de PostgreSQL, por lo que se está preparando una optimización local acotada para no repetir la espera de Redis por cada evento del mismo commit. Aún no está incluida en el SHA servido.

La auditoría también encontró un desajuste en código: el modelo declara índices del outbox para recuperación/reintentos que no aparecen en las migraciones revisadas. El esquema real, el volumen del outbox y su plan de consulta no se verificaron; no se infiere que esos índices falten en la base desplegada. El pool permite esperar hasta 15 s y hoy no registra métricas de tiempo esperando checkout; es un riesgo posible, no una causa confirmada.

El Render Free puede agregar hasta 50 s o más tras inactividad. La caída de Redis no explica por sí sola la lentitud de las lecturas bajo la configuración de producción, que desactiva la caché de modelos; sí puede añadir espera al camino síncrono de publicación de eventos de escrituras. No hay telemetría suficiente para atribuir toda la lentitud a una causa única.

## Límites

- Dominio compartido etiquetado como producción; el aislamiento de datos marcados `QA-OP` no está verificado.
- No se registraron cobros, gastos, reservas, permisos ni otros cambios; no se enviaron correos ni se activaron webhooks u OTAs.
- El envío final de un cobro requiere que el usuario lo confirme en el navegador; esta pasada solo observó pantallas de lectura.
- La simulación local no fue accesible desde la auditoría: Uvicorn aparece como proceso, pero no hay listener en `127.0.0.1:8041` y el agente recibió `ConnectionRefused`. No se reinició ni interrumpió ningún proceso.
- La matriz completa de roles, los flujos de escritura, el plan PostgreSQL y el p95/p99 siguen sin verificarse. Esta corrida no sirve como evidencia de release.

## Validación local del parche de outbox

El parche candidato corta los intentos síncronos de eventos durables después del primer fallo de publicación del lote. Las filas posteriores permanecen pendientes y la prueba verifica su reproducción por el worker con el mismo `event_id`; también cubre el retorno `None` del publicador degradado. Los eventos efímeros todavía se intentan.

- Suite backend local completa: **2841 passed, 34 skipped, 12 xfailed, 49 warnings** (`pytest -q`, 342.48 s).
- Suite focalizada adicional tras el cambio: eventos de dominio, recuperación del outbox y borrado lógico de habitaciones; **40 passed**.
- El primer pase completo reveló un doble de prueba antiguo que devolvía `None` mientras esperaba publicación exitosa. Se corrigió el doble en `tests/test_guest_restriction_api.py`; el segundo pase completo quedó verde.
- Estas pruebas usan fixtures locales/SQLite y no validan la latencia real de Redis/PostgreSQL. El parche sigue fuera del SHA `0174f497` servido en producción hasta ser integrado y desplegado.
