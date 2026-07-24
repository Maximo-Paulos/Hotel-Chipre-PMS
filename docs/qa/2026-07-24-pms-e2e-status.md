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
| Frontend build | Pasa. Vite informa un bundle principal de ~758 kB minificado; queda como deuda de performance. |
| Frontend lint | Pasa sin warnings. |
| E2E desktop | 19/19 pasan en Chromium, incluyendo login, logout, admin, calendario de tarifas, configuración del hotel y páginas V72. |
| E2E mobile | 2/2 pasan con viewport iPhone 13 sobre Chromium: sin overflow horizontal y navegación móvil a Reservas. |
| Backend focalizado | 14/14 pasan: stock, RLS de tenants y comprobantes de transferencia. |
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
saldo fallback incorrecto antes de reemplazarlo por el valor real. Debe
mostrarse un estado de carga en lugar de un cero provisional.

El hotel de QA no exponía controles para habilitar Mercado Pago ni
Transferencia, por lo que el editor de reserva ofrecía solo Efectivo y Débito.
La configuración local ahora incorpora toggles de medios de pago para el dueño;
Transferencia queda documentada como flujo con comprobante y aprobación.

## Limitaciones actuales

- La prueba móvil automatizada emula el viewport de iPhone en Chromium; no es
  una prueba de Safari/WebKit ni de un dispositivo físico.
- El navegador interno no pudo capturar screenshot del dashboard durante esta
  sesión por timeout de captura; la evidencia de layout se obtuvo mediante DOM
  y métricas de viewport.
- El despliegue de la rama y la repetición de QA contra el preview/cloud aún
  no están realizados.
- Sigue pendiente el recorrido completo de onboarding, habitaciones,
  categorías/tarifas, reservas, check-in/out, caja, pagos mixtos, comprobantes,
  Mercado Pago simulado, reportes, OTA, lavandería, permisos y carga.

## Próximo gate

Desplegar el preview con la rama aislada, repetir el smoke web/móvil contra ese
preview y continuar el recorrido de negocio con datos de prueba aislados.
Recién después ejecutar las pruebas de concurrencia y el gate de release.
