# QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE

**Fecha:** 2026-10-05
**Alcance:** comprobación posterior al merge de PR #119 sobre los dominios compartidos de la aplicación.
**SHA observado:** `790d7a1975541eda2a6906d90d33f76e62431d2a`.

## Runtime

- `https://api.hotels-pms.com/health`: HTTP 200 y SHA `790d7a1`.
- `https://api.hotels-pms.com/health/ready`: HTTP 200; PostgreSQL conectado y Redis desconectado. La ruta crítica de bloqueo usa advisory locks de PostgreSQL.
- `https://app.hotels-pms.com/build-meta.json`: HTTP 200 y el mismo SHA.
- El SHA del frontend, el API y `main` coincide. Esto confirma qué versión respondió durante la comprobación, no equivale a una aprobación de release.

## Comprobación visible de la aplicación

Se observaron sesiones de Dueño, Gerencia y Recepción. No había sesiones abiertas de Codueña, Limpieza ni Master Admin, por lo que esos roles quedan sin verificar.

Tiempos aproximados desde navegación hasta ver el encabezado de la pantalla, medidos en una sola pasada desde el navegador:

| Rol | Pantalla | Tiempo |
|---|---|---:|
| Gerencia | Dashboard | 553 ms |
| Gerencia | Habitaciones | 1.775 ms |
| Gerencia | Reservas | 1.135 ms |
| Gerencia | Tareas | 1.902 ms |
| Gerencia | Planilla | 3.010 ms |
| Recepción | Reservas | 1.412 ms |

En la vista de Reservas de Recepción aparecieron indicadores de carga transitorios; en la observación posterior se mostraron 33 filas, sin estado de error, vacío o carga activa. Estos son tiempos de encabezado de una sola muestra: no son percentiles ni mediciones completas de API/SQL y no prueban una mejora de rendimiento.

## Integridad de datos y pagos

No se enviaron cobros ni se modificaron reservas o caja. La caja visible contiene movimientos históricos y el endpoint de cobros crea asientos persistentes; un cobro en efectivo también cambia el saldo esperado. No hay un mecanismo seguro de borrar el asiento: corregirlo requiere una devolución auditada. La guía de QA de dominios compartidos prohíbe usar cobros reales como datos de prueba.

La interfaz no ofrece los métodos manuales Mercado Pago/PayPal. La revisión local encontró que el endpoint aún los aceptaba sin una respuesta verificada del proveedor; se está preparando una corrección local que los rechaza y preserva los flujos de pago válidos. Ese caso no se probó mediante una escritura en la nube.

## CI y límites de la evidencia

En PR #119, backend, frontend, preview contract y Vercel preview pasaron. Un run E2E pasó con 176 pruebas aprobadas y 6 omitidas; otro tuvo 174 aprobadas, 6 omitidas y 2 fallos con selectores ambiguos de habitaciones. Los mismos tests pasaron en el otro run del mismo SHA; los fallos no demuestran por sí solos un defecto funcional y requieren endurecer selectores y repetir con fixtures aislados.

Los controles `operating-system` y `trusted-base-evidence` quedaron bloqueados por falta de evidencia de QA aislada elegible. No se configuró ni utilizó Render QA, siguiendo la instrucción de hacer las pruebas localmente y evitar ese servicio.

## Pendientes

- Repetir los casos E2E fallidos con identidad exacta de habitación y datos aislados.
- Medir distribución de tiempos y solicitudes por interacción; esta revisión solo tiene muestras de encabezado.
- Validar el flujo de pagos con proveedores simulados localmente; no registrar pagos en el libro compartido.
- Completar cobertura cuando estén disponibles las sesiones de Codueña, Limpieza y Master Admin.
- Investigar con PostgreSQL aislado el costo de los sondeos del outbox y de la bandeja de acciones pendientes antes de cambiar índices o consultas.
