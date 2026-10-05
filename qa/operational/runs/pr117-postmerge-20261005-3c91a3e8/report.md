# QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE

## Resumen ejecutivo

Se comprobó de forma visible el despliegue posterior al cierre del PR #117 usando solo las sesiones abiertas de Dueño, Gerencia y Recepción. `/health` y `/build-meta.json` informan el mismo SHA integrado: `e36f1d90daf415858fb4a44cdcacdca17d4a750c`.

El Dashboard terminó de cargar para Dueño y Gerencia. Caja cargó en Dueño, pero la sesión de Gerencia recibió acceso denegado; queda pendiente cotejarlo con los permisos efectivos configurados para ese hotel. En Recepción, el detalle de una reserva sintética abrió, pero el resumen financiero mostró un error persistente. La solicitud de solo lectura a `/api/payments/summary/{reservation_id}` devolvió HTTP 403 en los intentos observados. El rol tiene `cash:operate` en la matriz predeterminada del código; no se pudo verificar si la cuenta del hotel tiene una anulación personalizada. No se registraron cobros, gastos ni cambios de reserva.

La preparación del backend figura lista con Postgres conectado y Redis desconectado en modo degradado. Esto coincide con un riesgo de latencia en la publicación de eventos después del commit. El arreglo local de refresh analítico dirigido reduce trabajo de escritura, pero todavía no está desplegado. Esta navegación no mide una escritura real en la nube.

## Cobertura observada

| Rol | Área | Observación | Estado |
|---|---|---|---|
| Dueño | Dashboard | Los estados de carga inicial terminaron y quedaron visibles los indicadores y la bandeja operativa. | PASS |
| Dueño | Caja | Cargaron resumen diario, conciliación por turno, movimientos y controles de cierre. No se ejecutó ninguna acción. | PASS, lectura solamente |
| Gerencia | Dashboard | Los estados de carga terminaron y quedaron visibles los indicadores y la bandeja operativa. | PASS |
| Gerencia | Caja | La ruta mostró “No tenés permiso para ver esta sección”. No se modificaron permisos. | NEEDS-VERIFICATION |
| Recepción | Reserva sintética | Abrió la ficha y sus controles operativos. El resumen financiero mantuvo “No se pudo cargar el resumen financiero”; la API de resumen respondió HTTP 403. No se registró cobro. | FAIL — permiso efectivo por verificar |

## Salud del despliegue

- `GET https://api.hotels-pms.com/health`: estado `ok`, SHA `e36f1d90daf415858fb4a44cdcacdca17d4a750c`.
- `GET https://app.hotels-pms.com/build-meta.json`: mismo SHA.
- `GET https://api.hotels-pms.com/health/ready`: Postgres `connected`; Redis `connected=false`; servicio listo en modo degradado y lock crítico respaldado por advisory lock de PostgreSQL.
- No se usó Render QA ni se consultó la base de datos del proveedor.

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
