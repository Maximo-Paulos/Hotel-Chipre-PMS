# Evidencia QA cloud — barrido funcional 2026-07-24

## Identificación

- Persona: owner QA autenticado.
- Dispositivo: navegador interno, viewport por defecto; intento Apple de 375×812.
- URL observada: `https://app.hotels-pms.com`.
- `code_sha` local bajo prueba: `91d5845`.
- SHA desplegado en cloud: no expuesto por el proveedor (`needs-verification`).
- Tipo de recorrido: lectura visible y una mutación controlada de huésped
  sintético; sin reserva, cobro ni integración externa.

## Recorrido y resultado

| Superficie | Esperado | Observado | Severidad |
| --- | --- | --- | --- |
| Dashboard, Reservas, Huéspedes, Habitaciones | Shell y datos operativos visibles | Cargan y muestran navegación/controles; algunas secciones muestran carga transitoria | P2 pendiente de repetir con trazas |
| Caja, Stock, Lavandería | Superficie operativa usable | Cargan sin error visible después de esperar la respuesta | Aprobado sólo como smoke |
| Reportes | Reporte diario y alertas visibles | `No se pudo cargar el reporte: Failed to fetch`; también aparece `No hay datos para mostrar` | P1 |
| Analytics y Analytics/Operación | Métricas o error accionable | Permanece en `Cargando analytics...` después de aproximadamente 14 segundos | P1 |
| Reserva rápida y cotización | Crear huésped, seleccionar categoría/fechas y ver total antes de confirmar | El huésped sintético se creó y recibió un ID; con categoría y fechas seleccionadas, el build publicado mantiene `Noches 0`, `Total final $ 0` y el mensaje inicial de cotización después de más de 10 segundos. La reserva no se confirmó. | P1 |
| Conexiones | Estado de proveedores y errores comprensibles | Gmail informa que Google no devolvió un token válido; Mercado Pago figura no conectado; WhatsApp figura revocado | P2 de configuración, sin acción externa |
| Pruebas de Mercado Pago | Formulario de prueba sin side effects no autorizados | Formulario visible; no se creó ningún link porque no se completó ni ejecutó la prueba | Pendiente provider-bound |

## Apple móvil

Se intentó aplicar 375×812. El navegador interno reportó 655 px efectivos, por
lo que esa medición no certifica un iPhone. No se usó como evidencia de ausencia
de overflow ni se modificó la sesión cloud. La certificación Apple válida queda
en la suite local WebKit; Safari nativo sigue pendiente.

## Restricciones respetadas

No se crearon reservas, pagos, comprobantes, links de Mercado Pago, emails,
webhooks, acciones OTA ni cambios de configuración. Se creó únicamente un
huésped sintético para probar el formulario rápido; el ID quedó en la sesión
QA del hotel y debe limpiarse mediante la política de fixtures antes de una
nueva corrida mutante. No se guardaron
credenciales, cookies, tokens, PII ni capturas con datos de la sesión.

## Evidencia disponible y limitación

La evidencia de este barrido es la URL y el DOM visible capturado durante cada
estado. El backend de captura del navegador interno no entregó un screenshot
persistible en este recorrido; por eso el campo de screenshot queda pendiente y
no se considera que la puerta funcional esté aprobada.

## Próximo paso

Desplegar el SHA actual de la rama a un preview aislado con PostgreSQL/Redis configurados,
obtener una traza del request autenticado de Reportes/Analytics y repetir el
barrido con una matriz completa, screenshots sanitizados y una cotización visible
antes de permitir confirmar la reserva.

## Revalidación owner con navegador interno — continuación

- Fecha: 2026-07-24.
- Persona: owner QA autenticado; no se probó una vista de rol como sustituto de
  una sesión real.
- Código local revisado: `aa8b60d`; SHA efectivamente desplegado: `needs-verification`.
- Tipo de recorrido: lectura visible, consulta de disponibilidad y apertura del
  formulario de reserva sin confirmar ninguna mutación financiera.

| Superficie | Resultado visible | Evaluación |
| --- | --- | --- |
| Dashboard | Renderiza reservas próximas y bandeja operativa; queda una sección de acciones en carga durante el smoke. | Smoke P2 pendiente de traza |
| Reservas | Renderiza 13 reservas y 12 acciones operativas abiertas; muestra reservas `unassigned`, saldos pendientes y duplicación de acciones para algunos códigos. | P1 operativo pendiente de conciliación |
| Consulta de disponibilidad | Para `Compartida QA Codex (#7)` del 2026-07-30 al 2026-07-31 muestra `Disponibles: 1`. | Smoke aprobado |
| Reserva rápida | Las categorías tardan aproximadamente 10 segundos en aparecer. Luego de seleccionar `Compartida QA Codex (#7)` y las fechas 2026-07-30/31, el formulario permanece en `Noches 0`, `Total final $ 0` y el mensaje inicial de cotización. | P1 reproducible |
| Caja, Stock y Lavandería | Renderizan sus superficies operativas sin error visible en el recorrido corto; no se abrió caja ni se registraron movimientos en este recheck. | Sólo smoke |
| Reportes | Reproduce `No se pudo cargar el reporte: Failed to fetch` y `No hay datos para mostrar.` | P1 reproducible |
| Analytics/Operación | Después de aproximadamente 12 segundos termina en `No se pudo cargar analytics.`; el navegador no expuso logs de error visibles. | P1; falta traza autenticada |
| Configuración de usuarios | Sólo aparece el owner. El formulario de invitación existe, pero no se envió ninguna invitación. | Personas manager/reception/housekeeping no verificadas |
| Conexiones y pruebas | Mercado Pago no conectado y WhatsApp revocado; la pantalla de pruebas describe links enviados por Gmail. No se creó ningún link ni se activó integración. | Pendiente provider-bound |

La pestaña del navegador fue dejada en el flujo cloud de QA para handoff. No se
guardaron screenshots persistibles; el backend de captura sigue sin producir
evidencia visual, por lo que esta revalidación no cierra la puerta funcional.

No se crearon huéspedes nuevos, reservas, pagos, comprobantes, links, emails,
webhooks, acciones OTA, invitaciones ni cambios de configuración durante esta
continuación.
