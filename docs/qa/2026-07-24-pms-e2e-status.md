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
| Frontend lint/typecheck/build | Pasan. Vite informa un bundle principal de ~778 kB minificado; queda como deuda de performance. |
| E2E desktop | 20/20 pasan en Chromium, incluyendo login, logout, admin, calendario de tarifas, configuración del hotel, el journey de negocio y páginas V72. La ejecución fresh completa queda en 22/22 al sumar móvil. |
| E2E mobile | 2/2 pasan con Chromium emulando iPhone y verificando 375×812, 390×844 y 430×932: sin overflow horizontal y navegación móvil a Reservas. |
| Backend completo | 1209 pasan, 17 se omiten, 12 quedan xfail y 1 xpass en Python 3.12 limpio. El runner E2E rechaza explícitamente Python menor a 3.10. |
| Migración virgen | `alembic upgrade head` pasa sobre SQLite temporal hasta `20260724_payment_proof_blobs`, incluyendo blobs privados, rotación y custodia. |
| Backend focalizado | 56/56 pasan: motor de asignación, operaciones de reservas, check-in, check-out y seguridad del flujo. |
| Analítica y trazabilidad | 27/27 pasan en contratos/API; cada envelope expone `data_as_of`, `source_lag_seconds` y `data_source`, y la UI lo muestra. |
| Aislamiento/cache/concurrencia | 56/56 pasan en aislamiento multi-hotel, cache con fallback PG y locks Redis/Valkey; caja y allocation quedaron protegidos. |
| Health de infraestructura | `/health/datastores` diferencia cache Redis de locks distribuidos y reporta si el lock es requerido. |
| Realtime multi-tab/warehouse/tenant keys | Contrato local de revisiones Redis, SSE autenticado, `BroadcastChannel` tenant-scoped, dimensiones y hechos ClickHouse PII-free de reservas/pagos/caja/stock, read model materializado idempotente, reconciliación de conteo+importe y FKs compuestas `(hotel_id, id)` en los vínculos core. |
| Runtime IaC | `render.yaml` declara autoscaling 3–50 (CPU 60%, memoria 70%), Valkey persistente privado, worker/beat separados y migración Alembic pre-deploy; provider sync/telemetría no verificados. |
| Load runner | `scripts/scale/staged_http_load.py` validado por tests y help; no ejecutado contra provider por falta de preview aislado. |
| Graphify | `portable-check` pasa después de actualizar y normalizar el grafo; `check-update` reporta pendiente semántico porque no se generaron descripciones/labels LLM en este run. |

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

En la medición de sólo lectura del cloud compartido, el dashboard sigue
reportando `scrollWidth=461` con viewport de 390 px. Es evidencia del build
desplegado allí, no del código local de esta rama; queda pendiente verificar el
fix después de un preview/provider-bound o un despliegue autorizado.

### Stock / egresos

En QA se probó de punta a punta la creación de una ubicación, la creación de un
item y el registro de un egreso. El flujo funciona, pero la UX era poco clara:
el egreso se iniciaba en un formulario separado, no mostraba stock actual y
permitía terminar en stock negativo sin advertencia.

La UI ahora agrega acciones rápidas por item, muestra el stock seleccionado y
obliga el motivo para egresos/ajustes. El backend rechaza egresos que dejarían
stock negativo y bloquea el item durante la comprobación para evitar que dos
operadores descuenten la misma existencia en paralelo.

La prueba creó datos identificables con prefijo `QA móvil` en el hotel de
prueba. Quedan pendientes de limpieza o de una política explícita de fixtures
reutilizables antes de repetir pruebas mutantes en el mismo hotel.

### Pagos y caja

Una reserva existente permitió comprobar el circuito de seña, pago total y
balance: el saldo pasó de `$31.500` a `$0` y, con una caja abierta, el pago
efectivo generó un ingreso de `$80.000` y un arqueo esperado de `$80.000`.
Cuando no hay caja abierta, el cobro efectivo ahora se rechaza para evitar
aprobar dinero fuera del arqueo. El cierre crea una caja sucesora con saldo
inicial `$0`, registra la entrega de custodia y permite que el dueño confirme
la recepción.

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

Los comprobantes de transferencia quedan pendientes hasta aprobación, se
normalizan a JPEG/PNG/WebP sin EXIF, se limitan a 5 MB, se hashean después del
re-encode y sus bytes viven en `payment_proof_blobs`, separado de la metadata y
protegido por tenant/RLS. La aprobación es idempotente y deja auditoría del
actor y del cambio de estado. La ficha permite ver la imagen privada y
rechazarla con motivo desde la misma revisión.

La caja ahora expone el último arqueo y el reporte de custodia; la sucesora se
crea automáticamente con saldo inicial `$0` incluso si el arqueo queda con
diferencia pendiente. La aprobación de la diferencia y la recepción de
custodia quedan separadas y la recepción sólo puede confirmarla el dueño.

El contrato de tokens de cotización también rechaza codificaciones Base64URL no
canónicas: cambiar bits sobrantes del último carácter ya no puede reutilizar la
misma firma decodificada.

### Inicialización concurrente de permisos

El E2E fresh expuso una carrera real: dos requests podían sembrar la matriz de
permisos a la vez y chocar contra `permissions.code`. Se agregó una regresión
con dos sesiones SQLite y el seed ahora usa inserciones atómicas con conflicto
ignorado para SQLite/PostgreSQL, conservando la reparación de descripciones y
valores por defecto. El caso y la suite completa quedan verdes.

### Journey de negocio local

Se agregó un E2E aislado que crea una categoría y una habitación, crea un huésped
rápido con documento, registra una reserva con seña manual, cobra un parcial en
efectivo, envía un comprobante de transferencia, lo aprueba y cobra el saldo
restante en efectivo antes de completar check-in/check-out. El flujo pasa en 1/1
y forma parte de la suite completa 22/22. El fixture de imagen se genera con un
contenido único por ejecución para no falsear la protección anti-duplicados.

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

### Frescura de analítica y concurrencia

Los endpoints `/api/analytics/*` ahora normalizan respuestas cacheadas y de
PostgreSQL con `data_as_of`, `source_lag_seconds` y `data_source`. La pantalla
de cada reporte muestra la fuente y el atraso, sin presentar una lectura
cacheada como tiempo real. El contrato conserva la posibilidad de informar
ClickHouse cuando exista un read model de warehouse con metadata propia.

Los cierres de caja usan el lock `lock:cash_close:{hotel_id}:{session_id}` y
la redistribución usa `lock:allocation:{hotel_id}`. El lease libera solo si el
token pertenece al worker actual; la base mantiene los locks de fila como
segunda barrera. En producción la configuración falla al iniciar si los locks
distribuidos no están habilitados y requeridos.

## Limitaciones actuales

- La prueba móvil automatizada emula el viewport de iPhone en Chromium; no es
  una prueba de Safari/WebKit ni de un dispositivo físico.
- En el cloud compartido, la lectura actual del dashboard mostró overflow
  horizontal (`461 px` de contenido contra `390 px` de viewport). No se
  modificó ese entorno ni se usa como sustituto de un preview aislado.
- El navegador interno no pudo capturar screenshot del dashboard durante esta
  sesión por timeout de captura; la evidencia de layout se obtuvo mediante DOM
  y métricas de viewport.
- El validador del manifiesto de ejemplo pasa, pero no existe un manifiesto
  provider-bound aislado para este SHA; el despliegue de la rama y la repetición
  de QA contra el preview/cloud aún no están realizados.
- El journey central de onboarding operativo, habitaciones, categoría, reserva,
  pagos mixtos (efectivo + comprobante de transferencia aprobado), check-in/out
  ya pasa localmente; siguen pendientes en el preview aislado el Mercado Pago simulado,
  reportes, OTA, lavandería, carga y la repetición cloud de todo el ciclo. El
  contrato local de permisos pasa y su seed ya está protegido contra carreras.
- No hay evidencia provider-bound para 10.000 hoteles, 10.000 usuarios
  concurrentes ni burst de 20.000: falta preview aislado, PostgreSQL co-local,
  Redis/Valkey administrado, ClickHouse real con CDC/reconciliación, carga
  instrumentada, autoscaling y métricas p95/p99. El ledger está en
  [`docs/data-foundations/scale-readiness.md`](../data-foundations/scale-readiness.md).
- La UI de analítica fue validada por build y contratos API, pero todavía no se
  repitió el journey completo contra un preview provider-bound.
- El warehouse local incluye replay acotado cada cinco minutos y reconciliación
  nocturna sobre PostgreSQL. Esto no prueba ClickPipes CDC ni el lag del
  proveedor: esas mediciones siguen pendientes en un preview aislado.

## Próximo gate

Provisionar el preview aislado con sus proveedores, repetir el smoke web/móvil
y el recorrido de negocio con datos de prueba aislados. Recién después ejecutar
las pruebas de carga/concurrencia y el gate de release; no usar el manifiesto de
ejemplo como evidencia de despliegue.
