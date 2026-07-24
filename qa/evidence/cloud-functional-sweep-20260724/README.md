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
