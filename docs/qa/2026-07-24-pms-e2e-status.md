# QA E2E del PMS — 2026-07-24

## Alcance

Auditoría incremental del flujo operativo del PMS en la rama
`codex/feature/pms-e2e-scale-hardening`. La prueba combina tests automatizados
locales con una sesión autorizada en el entorno web de QA abierto en el
navegador interno.

No se guardaron credenciales, cookies, tokens ni datos personales en el
repositorio.

## Evidencia automatizada

| Área | Resultado |
| --- | --- |
| Frontend lint/typecheck/build | Pasan. Vite informa un bundle principal de ~760 kB minificado; queda como deuda de performance. |
| E2E desktop | 20/20 pasan en Chromium, incluyendo login, logout, admin, calendario de tarifas, configuración del hotel, el journey de negocio y páginas V72. |
| E2E mobile | 2/2 pasan con viewport iPhone 13 sobre Chromium: sin overflow horizontal y navegación móvil a Reservas. |
| Backend completo | 1174 pasan, 17 se omiten, 12 quedan xfail y 1 xpass en Python 3.12 limpio. El `.venv` legado no puede importar el código por usar un Python anterior. |
| Migración virgen | `alembic upgrade head` pasa sobre SQLite temporal hasta `20260724_allocation_enum_values`. |
| Backend focalizado | 56/56 pasan: motor de asignación, operaciones de reservas, check-in, check-out y seguridad del flujo. |
| Graphify | `portable-check` y `check-update` pasan después de actualizar el grafo. |

## Hallazgos y correcciones

### Dashboard responsive

La sesión web de QA, medida a 390 px, mostraba `documentScrollWidth=558`:
la navegación y la tabla de próximas reservas desbordaban la pantalla. Se
corrigió el frontend para:

- presentar las reservas como tarjetas en móvil;
- mantener la tabla horizontal solo para desktop;
- limitar los contenedores flex/grid con `min-w-0`;
- exponer también las rutas operativas en la navegación móvil.

La corrección está validada localmente, pero el entorno web de QA debe recibir
un despliegue antes de repetir la medición allí.

### Stock / egresos

En QA se probó de punta a punta la creación de una ubicación, la creación de un
item y el registro de un egreso. El flujo funciona, pero la UX era poco clara:
el egreso se iniciaba en un formulario separado, no mostraba stock actual y
permitía terminar en stock negativo sin advertencia.

La UI ahora agrega acciones rápidas por item, muestra el stock seleccionado,
obliga el motivo para egresos/ajustes y advierte cuando el movimiento dejará
stock negativo. El backend todavía permite stock negativo; bloquearlo o
permitirlo según configuración del hotel requiere una decisión contable antes
de cambiar el dominio.

La prueba creó datos identificables con prefijo `QA móvil` en el hotel de
prueba. Quedan pendientes de limpieza o de una política explícita de fixtures
reutilizables antes de repetir pruebas mutantes en el mismo hotel.

### Pagos y caja

Una reserva existente permitió comprobar el circuito de seña, pago total y
balance: el saldo pasó de `$31.500` a `$0` y, con una caja abierta, el pago
efectivo generó un ingreso de `$80.000` y un arqueo esperado de `$80.000`.
Cuando no hay caja abierta, el entorno cloud todavía muestra el aviso de que
el cobro no queda registrado; la rama agrega apertura automática para cerrar
ese hueco.

Durante la carga inicial de la ficha una consulta incompleta llegó a mostrar un
saldo fallback incorrecto antes de reemplazarlo por el valor real. La rama ahora
muestra “Cargando resumen financiero…” en la ficha, evita exportar el voucher
antes de tener el resumen y deshabilita acciones de cobro mientras el resumen
está pendiente.

La navegación del smoke E2E dejó de usar `pushState` artificial: recorre links
visibles del shell autenticado. El seed aislado declara plan Pro para que el
owner pueda recorrer también las rutas sujetas a ese entitlement.

El hotel de QA no exponía controles para habilitar Mercado Pago ni
Transferencia, por lo que el editor de reserva ofrecía solo Efectivo y Débito.
La configuración local ahora incorpora toggles de medios de pago para el dueño;
Transferencia queda documentada como flujo con comprobante y aprobación.

### Journey de negocio local

Se agregó un E2E aislado que crea una categoría y una habitación, crea un huésped
rápido con documento, registra una reserva con seña manual, cobra el saldo en
efectivo y completa check-in/check-out. El flujo pasa en 1/1 y forma parte de la
suite desktop 20/20.

Durante ese recorrido se detectó que la migración de asignación guardaba los
estados con nombres de enum en mayúsculas mientras los modelos usaban valores en
minúscula. La migración `20260724_allocation_enum_values` alinea SQLite y
PostgreSQL con el contrato del modelo y fue validada desde una base virgen.
También se incorporaron tipo y número de documento al huésped rápido para que
el check-in respete la configuración legal del hotel.

### Cotización única y consistencia de tarifas

La rama agrega una cotización backend única para reservas internas, booking
público y WhatsApp. Devuelve desglose, moneda, seña, total, revisión de precio,
vencimiento y un token HMAC de corta duración sin PII. La creación recomputa el
precio contra PostgreSQL, compara la revisión y rechaza tokens manipulados,
vencidos o emitidos antes de un cambio de tarifa. El snapshot de la reserva
conserva la revisión usada; la UI dejó de sumar tarifas en el navegador y envía
el token firmado.

El contrato tiene cobertura backend/API 25/25, incluyendo la prueba negativa de
cambio de tarifa y la superficie pública. La suite Chromium quedó serializada
porque el fixture E2E usa una única SQLite aislada y ahora contiene un journey
mutante; así el resultado 20/20 es reproducible y no depende de carreras entre
workers.

## Limitaciones actuales

- La prueba móvil automatizada emula el viewport de iPhone en Chromium; no es
  una prueba de Safari/WebKit ni de un dispositivo físico.
- El navegador interno no pudo capturar screenshot del dashboard durante esta
  sesión por timeout de captura; la evidencia de layout se obtuvo mediante DOM
  y métricas de viewport.
- El validador del manifiesto de ejemplo pasa, pero no existe un manifiesto
  provider-bound aislado para este SHA; el despliegue de la rama y la repetición
  de QA contra el preview/cloud aún no están realizados.
- El journey central de onboarding operativo, habitaciones, categoría, reserva,
  cobro efectivo, check-in/out ya pasa localmente; siguen pendientes en el
  preview aislado los pagos mixtos, comprobantes, Mercado Pago simulado,
  reportes, OTA, lavandería, permisos, carga y la repetición cloud de todo el
  ciclo.

## Próximo gate

Desplegar el preview con la rama aislada, repetir el smoke web/móvil contra ese
preview y continuar el recorrido de negocio con datos de prueba aislados.
Recién después ejecutar las pruebas de concurrencia y el gate de release.
