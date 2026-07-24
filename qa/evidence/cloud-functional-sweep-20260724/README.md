# Evidencia QA cloud — barrido funcional 2026-07-24

## Identificación

- Persona: owner QA autenticado.
- Dispositivo: navegador interno, viewport por defecto; intento Apple de 375×812.
- URL observada: `https://app.hotels-pms.com`.
- `code_sha` local bajo prueba: `b1f2bb5`.
- SHA desplegado en cloud: no expuesto por el proveedor (`needs-verification`).
- Tipo de recorrido: lectura visible y navegación; sin mutaciones de negocio.

## Recorrido y resultado

| Superficie | Esperado | Observado | Severidad |
| --- | --- | --- | --- |
| Dashboard, Reservas, Huéspedes, Habitaciones | Shell y datos operativos visibles | Cargan y muestran navegación/controles; algunas secciones muestran carga transitoria | P2 pendiente de repetir con trazas |
| Caja, Stock, Lavandería | Superficie operativa usable | Cargan sin error visible después de esperar la respuesta | Aprobado sólo como smoke |
| Reportes | Reporte diario y alertas visibles | `No se pudo cargar el reporte: Failed to fetch`; también aparece `No hay datos para mostrar` | P1 |
| Analytics y Analytics/Operación | Métricas o error accionable | Permanece en `Cargando analytics...` después de aproximadamente 14 segundos | P1 |
| Conexiones | Estado de proveedores y errores comprensibles | Gmail informa que Google no devolvió un token válido; Mercado Pago figura no conectado; WhatsApp figura revocado | P2 de configuración, sin acción externa |
| Pruebas de Mercado Pago | Formulario de prueba sin side effects no autorizados | Formulario visible; no se creó ningún link porque no se completó ni ejecutó la prueba | Pendiente provider-bound |

## Apple móvil

Se intentó aplicar 375×812. El navegador interno reportó 655 px efectivos, por
lo que esa medición no certifica un iPhone. No se usó como evidencia de ausencia
de overflow ni se modificó la sesión cloud. La certificación Apple válida queda
en la suite local WebKit; Safari nativo sigue pendiente.

## Restricciones respetadas

No se crearon reservas, huéspedes, pagos, comprobantes, links de Mercado Pago,
emails, webhooks, acciones OTA ni cambios de configuración. No se guardaron
credenciales, cookies, tokens, PII ni capturas con datos de la sesión.

## Evidencia disponible y limitación

La evidencia de este barrido es la URL y el DOM visible capturado durante cada
estado. El backend de captura del navegador interno no entregó un screenshot
persistible en este recorrido; por eso el campo de screenshot queda pendiente y
no se considera que la puerta funcional esté aprobada.

## Próximo paso

Desplegar `b1f2bb5` a un preview aislado con PostgreSQL/Redis configurados,
obtener una traza del request autenticado de Reportes/Analytics y repetir el
barrido con una matriz completa y screenshots sanitizados.
