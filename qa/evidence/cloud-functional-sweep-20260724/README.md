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

## Revalidación owner — navegador interno conectado y vista Apple

- Fecha: 2026-07-24.
- Persona: owner QA autenticado en hotel ID 4; no se usó el selector de rol como
  sustituto de sesiones manager, recepción o housekeeping.
- Código local revisado: `9fcbba6`; SHA efectivamente desplegado: `needs-verification`.
- Dispositivo: navegador interno con viewport explícito `390×844`.
- Tipo de recorrido: barrido visible, consulta de disponibilidad y un huésped
  sintético creado desde el formulario; la reserva no se confirmó.

| Superficie | Resultado observado | Evaluación |
| --- | --- | --- |
| Dashboard | Renderiza la operación, pero deja una bandeja de acciones pendiente durante el smoke corto. | Smoke cloud; requiere repetir con SHA provider-bound |
| Reservas | Renderiza 13 reservas, disponibilidad `3 habitaciones` para Standard QA del 2026-08-15 al 2026-08-17 y el formulario de reserva. | Disponibilidad aprobada; ciclo de reserva bloqueado por cotización |
| Huésped rápido | Creó el huésped sintético `ID 14` y lo asignó al formulario. | Mutación controlada, sin email ni reserva |
| Cotización | Con categoría Standard QA y fechas seleccionadas permanece en `Noches 0`, `Total final $ 0` y `Elegí categoría y fechas para calcular el precio desde Tarifas.`; se repitió con el huésped ID 14 y blur natural mediante Tab en ambos campos de fecha. | P1 reproducible |
| Reportes | Después de más de 20 segundos permanece en `Cargando reporte...`. | P1 reproducible |
| Analytics/Operación | Después de 10 segundos permanece en `Cargando analytics...`; no hubo logs de error visibles. | P1 reproducible; falta traza autenticada |
| Usuarios y roles | La pantalla muestra únicamente al owner y el formulario de invitación. | Roles cloud reales pendientes |
| Conexiones y pruebas | Mercado Pago no conectado, WhatsApp revocado; el formulario de pruebas se inspeccionó sin crear links ni enviar Gmail. | Pendiente provider-bound |

### Medición responsive cloud

Con viewport real del navegador `390×844`, la lectura de overflow devolvió:

| Ruta | Ancho de viewport | Ancho de documento | Resultado |
| --- | ---: | ---: | --- |
| `/dashboard` | 390 | 557–558 | Overflow P1 cloud |
| `/reservas` | 390 | 392 | Overflow P2 cloud |
| `/caja` | 390 | 390 | Sin overflow observado |
| `/operacion/stock` | 390 | 392 | Overflow P2 cloud |
| `/reportes` | 390 | 392 | Overflow P2 cloud |
| `/operacion/lavanderia` | 390 | 392 | Overflow P2 cloud |

En una lectura acotada de Lavandería se encontraron 18 controles visibles con
ancho o alto menor a 44 px sobre 47 elementos inspeccionados; incluye controles
de cabecera de 16–29 px y campos/botones operativos de 37–38 px. Es evidencia
cloud del build publicado, no atribución definitiva al código local hasta
desplegar el SHA actual.

El huésped ID 14 es sintético y quedó sin reserva asociada; la UI no expone en
este recorrido una eliminación rápida que permita limpiar el registro desde la
misma pantalla. No se crearon reservas, pagos, comprobantes, links, emails,
webhooks, acciones OTA, invitaciones ni cambios de configuración.

La vista quedó pendiente de handoff en `/reportes`. No se guardaron screenshots,
credenciales, cookies, tokens ni PII adicional; el backend de captura de
screenshots volvió a expirar, por lo que la evidencia visual persistible sigue
pendiente.

## Revalidación final del estado de errores cloud

La pestaña owner se reconectó nuevamente en el navegador interno el 2026-07-24
y mantuvo hotel ID 4. `/reportes` terminó, después de 10 segundos, en
`No se pudo cargar el reporte` junto con `No hay datos para mostrar`; luego
`/analytics/operations` terminó, después de 10 segundos, en `No se pudo cargar
analytics.`. La sesión siguió autenticada durante ambas lecturas. El SHA
desplegado continúa sin exposición (`needs-verification`), por lo que no se
atribuye todavía el fallo al commit local `60845ed`.

## Revalidación owner — disponibilidad y cotización, continuación

- Fecha: 2026-07-24.
- Persona: owner QA autenticado en hotel ID 4.
- Dispositivo: navegador interno con viewport por defecto; no se ejecutaron
  side effects externos.
- Código local revisado: `fb4be2d`; SHA efectivamente desplegado:
  `needs-verification`.

| Superficie | Resultado observado | Evaluación |
| --- | --- | --- |
| Consulta de disponibilidad | Se seleccionó `Standard QA (#5)`, se ingresaron 2026-08-15 a 2026-08-17 y se ejecutó `Consultar`; la UI devolvió `Disponibles: 3` e IDs 6, 7 y 11. | Disponibilidad responde, pero las fechas no quedan preservadas |
| Fechas después de consultar | Después de la respuesta, los campos volvieron a mostrar 2026-07-24 a 2026-07-25. Se reprodujo tanto con `fill` directo como con blur natural mediante Tab. | P1: la acción visible no conserva el rango consultado |
| Reserva rápida | En el formulario se seleccionó `Standard QA (#5)` y se ingresaron 2026-08-15 a 2026-08-17; el formulario permaneció en `Noches 0`, `Total final $ 0` y el mensaje inicial de cotización. | P1 reproducible; no se confirmó la reserva |
| Reportes y Analytics | Reportes y Analytics/Operación permanecieron en estados de carga durante este recorrido; no hubo logs visibles del navegador. | P1; falta traza autenticada del provider |

El formulario de reserva se cerró con `Cancelar` y no se crearon huéspedes,
reservas, pagos, comprobantes, links, emails, webhooks, invitaciones ni cambios
de configuración durante esta continuación.

## Revalidación owner — roles QA y disponibilidad del preview

- Fecha: 2026-07-24.
- Persona: owner QA autenticado en hotel ID 4.
- Tipo de recorrido: sólo lectura; no se invitó a nadie, no se enviaron emails y
  no se alteró configuración, reservas, pagos ni caja.
- SHA cloud desplegado: `needs-verification`.

| Superficie | Resultado observado | Evaluación |
| --- | --- | --- |
| Usuarios y roles | `/settings/users` muestra sólo el owner activo; el formulario de invitación existe pero quedó sin completar y sin enviar. | P1: faltan personas QA reales para manager, recepción y housekeeping |
| Selector de vista | El owner puede seleccionar Manager, Housekeeping y Recepción y vuelve al dashboard. Es una vista de previsualización del owner, no una sesión, membresía ni autorización independiente. | No sustituye el journey cloud de cinco personas |
| Preview QA local | `.env.qa.local` no está presente en el worktree y no se leyó ningún secreto. | No hay bootstrap local de sesión/provider para validar el preview |
| Variables GitHub `preview-qa` | La lectura de nombres mostró sólo identificadores de producción; no aparecen `RENDER_QA_SERVICE_ID` ni `SUPABASE_QA_PROJECT_REF`. | P1: no existe par frontend/backend/base aislado verificable |
| Workflow confiable | `Trusted preview QA cycle` está registrado, pero `gh run list` devolvió cero ejecuciones. | Falta evidencia provider-bound posterior al SHA funcional |

La sesión continuó autenticada como owner. No se guardaron contraseñas,
cookies, tokens, emails de invitación, screenshots privados ni valores de
variables de proveedor.

## Revalidación de contrato cloud y drift de despliegue

- Fecha: 2026-07-24.
- La lectura pública de `https://api.hotels-pms.com/openapi.json` devolvió HTTP
  200, 278 paths y declaró las rutas actuales de reportes operativos, analytics,
  cotización y disponibilidad.
- Las probes sin sesión de `/api/reports/operational/daily`,
  `/api/reports/operational/alerts`, `/api/analytics/home`,
  `/api/analytics/operations` y `/api/reservations/quote` devolvieron HTTP 401
  con `Autenticacion requerida`; no se usaron tokens para esta comprobación.
- La página pública de la app referencia el bundle
  `/assets/index-DkFkQnkh.js`; el build local validado de esta rama produce
  `frontend/dist/assets/index-Bzcjn1pR.js`. La diferencia demuestra drift de
  artefacto, pero no permite atribuir por sí sola el fallo a un commit concreto.
- Con la sesión owner QA visible, `/reportes` terminó después de 15 segundos en
  `No se pudo cargar el reporte: Failed to fetch` y `No hay datos para mostrar`;
  `/analytics/operations` terminó después de 15 segundos en `No se pudo cargar
  analytics.`.

La conclusión sigue siendo `needs-verification`: falta un preview aislado o un
SHA provider-bound que permita repetir el recorrido contra el artefacto exacto.
