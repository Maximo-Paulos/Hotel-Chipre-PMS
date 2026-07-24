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
| Frontend lint/typecheck/build | Pasan. Vite informa un bundle principal de 785.37 kB minificado (190.07 kB gzip); queda como deuda de performance. |
| E2E desktop | 23/23 pasan en Chromium, incluyendo login, logout, admin, calendario de tarifas, configuración del hotel, los journeys de negocio, la jornada de operaciones diarias y páginas V72. La ejecución fresh completa queda en 31/31 al sumar móvil Chromium y los tres perfiles WebKit. |
| E2E mobile | 2/2 pasan con Chromium emulando iPhone y verificando 375×812, 390×844 y 430×932; 6/6 pasan con Playwright WebKit en perfiles iPhone SE, iPhone 15 y iPhone 15 Pro Max; los journeys mutantes de reserva/pagos/check-in/out, inventario, cambio de habitación/no-show y operaciones diarias pasan 4/4 en WebKit iPhone 15. Esto no sustituye Safari nativo del simulador Xcode, que no está disponible en este host. |
| Backend completo | 1220 pasan, 17 se omiten, 12 quedan xfail y 1 xpass en Python 3.12 limpio. El runner E2E rechaza explícitamente Python menor a 3.10. |
| Forward-tests de arquitectura de datos | 2/2 pasan: una entidad de otro hotel no puede leerse ni adjuntarse, y una cotización queda invalidada antes de persistir la reserva cuando cambia la tarifa. |
| Migración virgen | `alembic upgrade head` pasa sobre SQLite temporal hasta `20260724_room_move_enum_values`, incluyendo blobs privados, rotación, custodia, claves tenant restantes y el contrato de movimientos de habitación. |
| Backend focalizado | 56/56 pasan: motor de asignación, operaciones de reservas, check-in, check-out y seguridad del flujo. |
| Analítica y trazabilidad | 27/27 pasan en contratos/API; cada envelope expone `data_as_of`, `source_lag_seconds` y `data_source`, y la UI lo muestra. |
| Aislamiento/cache/concurrencia | 56/56 pasan en aislamiento multi-hotel, cache con fallback PG y locks Redis/Valkey; caja y allocation quedaron protegidos. |
| Health de infraestructura | `/health/datastores` diferencia cache Redis de locks distribuidos y reporta si el lock es requerido. |
| Realtime multi-tab/warehouse/tenant keys | Contrato local de revisiones Redis, SSE autenticado, `BroadcastChannel` tenant-scoped, dimensiones y hechos ClickHouse PII-free de reservas/pagos/caja/stock, read model materializado idempotente, reconciliación de conteo+importe y FKs compuestas `(hotel_id, id)` en todo el grafo hotel-scoped. |
| Runtime IaC | `render.yaml` declara autoscaling 3–50 (CPU 60%, memoria 70%), Valkey persistente privado, worker/beat separados y migración Alembic pre-deploy; provider sync/telemetría no verificados. |
| Load runner | `scripts/scale/staged_http_load.py` validado por tests y help; no ejecutado contra provider por falta de preview aislado. |
| Graphify | `portable-check` pasa después de actualizar y normalizar el grafo; `check-update` reporta pendiente semántico porque no se generaron descripciones/labels LLM en este run. |
| Integridad financiera y warehouse | El ledger de transacciones gobierna validaciones/resumen de cobro, el endpoint directo exige `Idempotency-Key`, la tarifa batched acepta medio de pago y los hechos financieros proyectan solo transacciones confirmadas con reembolsos firmados. Contratos focalizados y regresiones pasan. |

### Smoke de la skill de navegador interno

La skill `browser:control-in-app-browser` quedó verificada con la pestaña QA
existente: reconoció la sesión autenticada sin volver a solicitar credenciales,
leyó el dashboard y navegó de forma read-only a `/reservas` y
`/operacion/tarifas`. Se observaron los controles de listado, filtros,
disponibilidad, calendario de tarifas y navegación operativa. No se crearon ni
modificaron reservas, pagos, tarifas o configuración durante este smoke. Como
interacción segura, se activó la vista `Mes`, se seleccionó el filtro
`Cancelada` y se restauró con `Limpiar`; el estado `[active]` y la opción
seleccionada quedaron visibles en el DOM después de cada acción.

El intento de aplicar un viewport explícito de 390×844 no produjo ese tamaño en
la sesión cloud (el navegador reportó su viewport efectivo), por lo que no se
usa como evidencia móvil. La evidencia móvil local sigue siendo Playwright
Chromium/WebKit con perfiles iPhone; Safari nativo requiere un host con
`xcrun simctl`.

Como smoke adicional del runner, el backend E2E local aislado respondió 6.322
requests `200` en steady (4 workers, p95 1,46 ms) y 2.840 requests `200` en
burst (8 workers, p95 4,91 ms), sin errores de transporte. Es una prueba de
funcionamiento del arnés sobre SQLite local, no evidencia de capacidad,
conexiones, SLO o autoscaling de provider.

La revisión de rendimiento local también encontró y corrigió un N+1 en la
consulta de habitaciones disponibles: una categoría con 20 habitaciones pasó
de 85 a 7 sentencias SQL en el fixture de regresión, manteniendo filtros de
hotel, bloqueos, reservas activas y `exclude_reservation_id`. El benchmark
PostgreSQL co-localizado y sus planes `EXPLAIN` siguen pendientes.

La combinación que recorre la jornada diaria y las páginas autenticadas quedó
en 14/14 en Chromium serial después de corregir la serialización del perfil
rápido de huésped. La ruta `GET /api/guests/{id}/quick-profile` devolvía
instancias ORM con relaciones cíclicas (`Guest.reservations` y
`GuestTag.guest`); después de crear una estadía, el encoder genérico de FastAPI
podía terminar en `RecursionError`. La API ahora convierte el huésped y sus
etiquetas a `GuestRead`/`GuestTagRead` JSON antes de responder, y una prueba de
regresión cubre un huésped con una estadía existente.

### Revalidación del goal funcional-first

La sesión autenticada del navegador interno se revalidó el 2026-07-24 con
lectura visible y sin mutaciones. `/dashboard`, `/reservas`,
`/operacion/tarifas` y `/analytics/operations` renderizan su shell; `/reportes`
falla de forma reproducible después de dos cargas y muestra:

`No se pudo cargar el reporte: Failed to fetch`

La carga fallida ocurre tanto para la fecha actual como después de una nueva
carga de la ruta. No hubo errores en la consola del navegador. El bundle
publicado contiene `https://api.hotels-pms.com/api` como base de API (no
localhost), `/health` respondió HTTP 200 desde el host de verificación y el
preflight CORS para `https://app.hotels-pms.com` respondió HTTP 200 con los
headers de autorización esperados. La causa raíz del request autenticado sigue
`needs-verification`: falta una traza del provider o evidencia de la respuesta
real de `/api/reports/operational/daily` y `/api/reports/operational/alerts`.

El intento de viewport explícito de 390×844 en la sesión cloud quedó en 655 px
efectivos, por lo que no se usa como certificación móvil. La suite local se
repitió desde cero con:

`E2E_PYTHON=/tmp/hpms-scale-venv-312/bin/python npm run e2e`

y terminó `31 passed (44.2s)`. Esto confirma el baseline local, pero no cierra
el fallo cloud, los cinco roles reales, el preview aislado ni Safari nativo.

El catálogo conserva gaps funcionales pendientes: onboarding/recuperación,
roles manager/reception/housekeeping con sesiones reales, caminos negativos de
reservas/caja/stock/reportes, tarifas contra backend real, analytics UI,
Mercado Pago simulado y evidencia provider-bound. No se declara aprobada la
puerta funcional mientras el reporte cloud permanezca sin diagnóstico.

## Hallazgos y correcciones

### Dashboard responsive

La sesión web de QA, medida a 390 px, mostraba `documentScrollWidth=558`:
la navegación y la tabla de próximas reservas desbordaban la pantalla. Se
corrigió el frontend para:

- presentar las reservas como tarjetas en móvil;
- mantener la tabla horizontal solo para desktop;
- limitar los contenedores flex/grid con `min-w-0`;
- exponer también las rutas operativas en la navegación móvil.

### Cotización vigente antes de crear una reserva

La matriz E2E completa reprodujo una carrera bajo concurrencia de proyectos:
el botón `Crear` podía aceptar un click mientras React Query todavía marcaba la
cotización como `isFetching`, por lo que no se enviaba la reserva aunque ya se
mostrara un total. Se corrigió bloqueando el submit hasta disponer de un
`quote_token` vigente y mostrando `Actualizando...`; el journey ahora espera
explícitamente el estado habilitado. La ejecución posterior quedó integrada en
la matriz fresh de 31/31.

La corrección está validada localmente, pero el entorno web de QA debe recibir
un despliegue antes de repetir la medición allí.

La ejecución del journey central en WebKit iPhone 15 primero detectó que el
helper E2E sólo buscaba el menú lateral desktop, que está oculto en viewports
móviles. El test fue adaptado para usar la navegación móvil visible; el
journey completo pasó 1/1 después de la corrección.

El primer intento de incluir ambos journeys mutantes en la misma corrida
reveló una colisión del arnés: Chromium y WebKit reseteaban la misma SQLite
aislada en paralelo. El proyecto WebKit quedó opt-in y documentado para
ejecutarse como una segunda corrida serial, preservando la reproducibilidad de
la suite por defecto.

En la medición de sólo lectura del cloud compartido, el dashboard sigue
reportando `scrollWidth=461` con viewport de 390 px. Es evidencia del build
desplegado allí, no del código local de esta rama; queda pendiente verificar el
fix después de un preview/provider-bound o un despliegue autorizado.

### Stock / egresos

En QA se probó de punta a punta la creación de una ubicación, la creación de un
item y el registro de un egreso. El flujo funciona, pero la UX era poco clara:
el egreso se iniciaba en un formulario separado, no mostraba stock actual y
permitía terminar en stock negativo sin advertencia.

La UI ahora usa acciones guiadas de Ingreso, Egreso y Ajuste, muestra el stock
actual y el resultado previsto, mantiene el ítem seleccionado para operaciones
repetitivas y permite asociar consumos buscando huésped o código de reserva en
lugar de introducir IDs. El motivo es obligatorio. El backend rechaza egresos
que dejarían stock negativo, bloquea el ítem durante la comprobación para evitar
que dos operadores descuenten la misma existencia en paralelo y separa los
permisos `stock:operate` y `stock:adjust`; la denegación del ajuste se audita.

El journey UI de inventario pasa 1/1 en Chromium y 1/1 en WebKit iPhone 15:
crea ubicación e ítem, registra ingreso, egreso, ajuste autorizado y verifica
que un egreso superior al disponible quede bloqueado antes de enviar.

La prueba creó datos identificables con prefijo `QA móvil` en el hotel de
prueba. Quedan pendientes de limpieza o de una política explícita de fixtures
reutilizables antes de repetir pruebas mutantes en el mismo hotel.

### Cambio de habitación y no-show

La ficha de reserva ahora expone un bloque guiado de `Operaciones de estadía`.
El operador puede elegir una habitación destino activa de la misma categoría,
informar motivo y notas, y ejecutar el cambio desde la ficha. La API conserva
la transición auditada y la UI muestra el número visible de la habitación, no
el identificador interno.

La misma ficha permite registrar un no-show para reservas pendientes o pagadas,
con notas y confirmación explícita. El estado queda representado como
`No-show` y no genera un cobro automático. El contrato frontend incluye la
versión optimista de la reserva para que el backend pueda rechazar cambios
obsoletos.

El journey crea dos habitaciones, crea una reserva asignada, mueve la reserva
con motivo/notas y luego registra el no-show. Pasa 1/1 en Chromium y 1/1 en
WebKit iPhone 15.

El primer intento reveló un defecto real en una base virgen: la migración de
movimientos había creado el constraint SQLite/enum PostgreSQL con nombres de
miembro en mayúscula, mientras el servicio persistía los valores en minúscula.
La nueva migración `20260724_room_move_enum_values` repara datos existentes y
alinea ambos motores con el contrato runtime; la prueba fresh vuelve a ejecutar
toda la cadena hasta `head`.

### Operaciones diarias: lista de espera, housekeeping, lavandería y reportes

El journey local de operaciones diarias pasa 1/1 en Chromium y 1/1 en WebKit
iPhone 15. Crea una entrada de lista de espera para una categoría existente,
la promueve a una reserva, cambia una habitación a `Limpieza`, crea un lote de
lavandería con item y habitación, y recorre `Recolectado → Enviado → Recibido
→ Cerrado`. Finalmente abre reportes, cambia la fecha y exige una respuesta
`200` de `/api/reports/operational/daily` junto con las secciones operativas
visibles. La aserción de lavandería observa la tarjeta del lote, que es donde
la UI representa el estado, además del mensaje de confirmación de cada cambio.

### Perfil rápido de huésped después de una estadía

La serialización del perfil rápido se validó con una reserva ya finalizada y
conserva el resumen de estadías sin exponer el grafo ORM de relaciones. El
contrato evita que una estadía existente cambie una respuesta válida en una
recursión infinita del encoder.

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

El journey mutante detectó además un problema de frescura en la UI: los pagos
de una reserva actualizaban el ledger y la caja en backend, pero la pantalla
de Caja podía conservar el resumen anterior en React Query. Los hooks centrales
de cobros manuales y aprobación de comprobantes ahora invalidan las consultas
de sesiones, movimientos, resumen y último cierre del hotel. La regresión pasa
en Chromium y en WebKit iPhone 15 con saldo esperado positivo antes del cierre.

El contrato de tokens de cotización también rechaza codificaciones Base64URL no
canónicas: cambiar bits sobrantes del último carácter ya no puede reutilizar la
misma firma decodificada.

### Consistencia financiera y de tarifas

La auditoría de arquitectura encontró dos divergencias locales que ya quedaron
cerradas con pruebas de regresión. `resolve_rate_calendar` ahora recibe el medio
de pago opcional y calcula `price` con el mismo override que
`get_price_for_date`; esto evita que el calendario batched elija arbitrariamente
el primer precio configurado. El endpoint directo `/api/payments` exige
`Idempotency-Key` y reentrega la misma transacción ante un reintento.

Las lecturas nuevas de resumen, validación de sobrepago/reembolso, links de pago,
check-in, checkout, reportes operativos y el proyector de hechos consultan
transacciones `completed`; los reembolsos se representan con signo negativo.
`Reservation.amount_paid` se conserva como caché materializada para compatibilidad
con reservas históricas, pero una reserva con movimientos en el ledger no usa ese
campo como autoridad. Los datos históricos sin transacciones todavía usan la
caché como fallback explícito y deben migrarse antes de exigir consistencia
financiera estricta.

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
restante en efectivo antes de completar check-in/check-out y cerrar la caja con
rotación de custodia. El flujo pasa en 1/1 por Chromium y 1/1 por WebKit iPhone
15, y forma parte de la suite completa 31/31. El fixture de imagen se genera con un
contenido único por ejecución para no falsear la protección anti-duplicados.

### Registro, verificación, recuperación y onboarding

El recorrido E2E ahora también crea un owner desde `/register-owner`, obtiene
los códigos mediante el outbox local no-op, verifica el email, completa los
nueve pasos del onboarding, cierra sesión, recupera la contraseña y vuelve a
iniciar sesión. Se corrigió un P1 donde el frontend intentaba guardar el owner
antes de verificar el email, y otro donde la hidratación asíncrona de métodos de
pago podía sobrescribir un click humano. El perfil pendiente sólo conserva
nombre, email, teléfono y rol en `sessionStorage`; nunca contraseña, token ni
cookie.

La regresión pasa en Chromium y la suite completa queda en 35/35 usando un
worker global sobre la SQLite aislada. La corrida con cinco workers reprodujo
un `database is locked` durante un cobro concurrente; por eso no se considera
evidencia funcional y las mutaciones locales se ejecutan serializadas.

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

### Revalidación cloud posterior con navegador interno

Con la sesión autenticada existente del navegador interno, hotel QA ID 4 y rol
Dueño, `/reportes` se abrió en una pestaña controlada nueva. En una carga fría
mostró `Failed to fetch`; en una repetición posterior permaneció en `Cargando
reporte...` durante más de 11 segundos. `/analytics/operations` también
permaneció en `Cargando analytics...` después de 13 segundos. No hubo errores ni
warnings visibles en la consola del navegador. La salud pública del API y el
preflight CORS responden, pero no existe todavía una respuesta autenticada ni
traza del proveedor para aislar si el problema es backend, proxy o consulta.
Esto mantiene ambos recorridos como bloqueadores funcionales P1 y requiere
evidencia del preview/proveedor antes de corregir a ciegas.

La ejecución fue de solo lectura: no se crearon reservas, pagos, comprobantes,
emails, webhooks ni cambios de configuración.

## Limitaciones actuales

- La prueba móvil automatizada emula viewports de iPhone en Chromium y WebKit;
  no es una prueba de Safari nativo ni de un dispositivo físico.
- En una lectura cloud anterior del dashboard se observó overflow horizontal
  (`461 px` de contenido contra `390 px` de viewport). El smoke actual no pudo
  aplicar de forma confiable ese viewport explícito; no se modificó ese entorno
  ni se usa como sustituto de un preview aislado.
- No se guardó screenshot del dashboard cloud en el repositorio; la evidencia
  del smoke se obtuvo mediante DOM visible y URL, sin persistir PII ni sesión.
- El validador del manifiesto de ejemplo pasa, pero no existe un manifiesto
  provider-bound aislado para este SHA; el despliegue de la rama y la repetición
  de QA contra el preview/cloud aún no están realizados.
- El journey central de onboarding operativo, habitaciones, categoría, reserva,
  pagos mixtos (efectivo + comprobante de transferencia aprobado), check-in/out,
  cierre de caja, inventario guiado, operaciones de estadía y operaciones diarias
  ya pasan localmente; siguen pendientes en el preview aislado el Mercado Pago
  simulado, OTA, carga y la repetición cloud de todo el ciclo. El contrato local
  de permisos pasa y su seed ya está protegido contra carreras.
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
- Las pruebas que mutan la SQLite local deben ejecutarse serializadas. La
  corrida paralela de cinco proyectos reprodujo `database is locked` durante
  un cobro; una corrida secuencial con `--workers=1` pasa 35/35. Una corrida
  paralela que arranque dos servidores E2E sobre el mismo archivo también puede
  fallar durante el reset con `table users already exists`; no es evidencia de
  un fallo funcional del PMS, pero sí una limitación del arnés local.

## Próximo gate

Provisionar el preview aislado con sus proveedores, repetir el smoke web/móvil
y el recorrido de negocio con datos de prueba aislados. Recién después ejecutar
las pruebas de carga/concurrencia y el gate de release; no usar el manifiesto de
ejemplo como evidencia de despliegue.
