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
| Frontend lint/typecheck/build | Pasan. Vite informa un bundle principal de 788.60 kB minificado (190.98 kB gzip); queda como deuda de performance. |
| E2E desktop | Pasan los journeys de Chromium de login, logout, admin, calendario de tarifas, configuración del hotel, negocio, operaciones diarias, consumos, páginas V72, estados accionables de Analytics y Reportes, error de cotización y ciclo de vida de reserva. La ejecución serial fresh completa queda en 52/52 al sumar móvil Chromium y los tres perfiles WebKit. |
| E2E mobile | 4/4 pasan con Chromium emulando iPhone y verificando 375×812, 390×844 y 430×932; 12/12 pasan con Playwright WebKit en perfiles iPhone SE, iPhone 15 y iPhone 15 Pro Max. La regresión de selector con nombre largo, touch targets críticos, overflow de páginas operativas, el journey de Reportes, consumos y el ciclo de vida de reserva en WebKit quedan cubiertos; la suite completa pasa 52/52. Esto no sustituye Safari nativo del simulador Xcode, que no está disponible en este host. |
| Backend completo | 1242 pasan, 17 se omiten, 12 quedan xfail y 1 xpass en Python 3.12 limpio. El runner E2E rechaza explícitamente Python menor a 3.10. |
| Forward-tests de arquitectura de datos | 2/2 pasan: una entidad de otro hotel no puede leerse ni adjuntarse, y una cotización queda invalidada antes de persistir la reserva cuando cambia la tarifa. |
| Migración virgen | `alembic upgrade head` pasa sobre SQLite temporal hasta `20260724_billing_adjustment_enum_values`, incluyendo blobs privados, rotación, custodia, claves tenant restantes, movimientos de habitación y el contrato de cargos operativos. |
| Backend focalizado | 56/56 pasan: motor de asignación, operaciones de reservas, check-in, check-out y seguridad del flujo. |
| Analítica y trazabilidad | 27/27 pasan en contratos/API; cada envelope expone `data_as_of`, `source_lag_seconds` y `data_source`, y la UI lo muestra. |
| Aislamiento/cache/concurrencia | 56/56 pasan en aislamiento multi-hotel, cache con fallback PG y locks Redis/Valkey; caja y allocation quedaron protegidos. |
| Health de infraestructura | `/health/datastores` diferencia cache Redis de locks distribuidos y reporta si el lock es requerido. |
| Realtime multi-tab/warehouse/tenant keys | Contrato local de revisiones Redis, SSE autenticado, `BroadcastChannel` tenant-scoped, dimensiones y hechos ClickHouse PII-free de reservas/pagos/caja/stock, read model materializado idempotente, reconciliación de conteo+importe y FKs compuestas `(hotel_id, id)` en todo el grafo hotel-scoped. |
| Runtime IaC | `render.yaml` declara autoscaling 3–50 (CPU 60%, memoria 70%), Valkey persistente privado, worker/beat separados y migración Alembic pre-deploy; provider sync/telemetría no verificados. |
| Load runner | `scripts/scale/staged_http_load.py` validado por tests y help; no ejecutado contra provider por falta de preview aislado. |
| Graphify | `portable-check` pasa después de actualizar y normalizar el grafo; `check-update` reporta pendiente semántico porque no se generaron descripciones/labels LLM en este run. |
| Integridad financiera y warehouse | El ledger de transacciones gobierna validaciones/resumen de cobro, el endpoint directo exige `Idempotency-Key`, la tarifa batched acepta medio de pago y los hechos financieros proyectan solo transacciones confirmadas con reembolsos firmados. Contratos focalizados y regresiones pasan. |

### Cobertura adicional del ciclo de reserva

En el commit `3cb353b` se agregó `frontend/e2e/reservation-lifecycle.spec.ts`.
La prueba crea datos sintéticos en la base E2E aislada, crea una reserva desde
la UI, edita y extiende el check-out, intenta una reserva superpuesta sobre la
misma habitación y verifica el rechazo visible, y finalmente cancela la
reserva. Pasó 1/1 en Chromium y 1/1 en WebKit iPhone 15. La suite serial fresh
completa posterior terminó `47 passed (1.5m)`.

No hubo cobros, comprobantes, emails, webhooks, OTA ni cambios en el entorno
cloud. La cobertura valida el recorrido local y no reemplaza la repetición en
un preview provider-bound aislado.

### Regresión móvil de superficies críticas

En el commit `60845ed` se amplió
`frontend/e2e/responsive-smoke.spec.ts` para cubrir explícitamente Reportes y
Lavandería, además de Reservas, Caja y Stock. La nueva aserción exige que el
ancho del documento y del body no supere el viewport de 390×844; la aserción
de controles táctiles exige una altura mínima de 44 px. La ejecución fresh
serial pasó 47/47 en Chromium móvil y WebKit iPhone SE, iPhone 15 y iPhone 15
Pro Max.

### Comprobantes de transferencia: rechazo y reintento

En los commits `a04728c` y `275058e` se amplió el journey financiero de
`frontend/e2e/business-journey.spec.ts`: después de un cobro parcial en
efectivo, el intento de sobrepago se rechaza, se carga un comprobante
sintético de transferencia, se lo rechaza con motivo visible, se reenvía una
imagen con hash distinto y se aprueba, y finalmente se registra una devolución
parcial en efectivo con confirmación antes de completar el saldo. El camino
pasó 4/4 en Chromium y 4/4 en el proyecto WebKit iPhone 15 de negocio
(`E2E_WEBKIT_BUSINESS=true`). Esto prueba desde la UI que las validaciones no
mutan el ledger, un rechazo no descuenta saldo, el reintento no reutiliza el
comprobante previo y la devolución reabre sólo el saldo devuelto.

La cobertura local todavía no reemplaza el preview provider-bound ni verifica
en la UI el link de Mercado Pago simulado y la repetición de webhooks; esos
puntos siguen pendientes junto con la conciliación cloud.

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
lectura visible y sin mutaciones. `/dashboard`, `/reservas` y
`/operacion/tarifas` renderizan su shell. `/analytics/operations` terminó
después de aproximadamente 12 segundos mostrando `No se pudo cargar
analytics.`; `/settings/subscription` mostró un plan Pro activo con 6/40
habitaciones, por lo que no se atribuye el fallo a un plan Starter. `/reportes`
falló de forma reproducible después de aproximadamente 15 segundos y muestra:

`No se pudo cargar el reporte: Failed to fetch`

La carga fallida ocurre tanto para la fecha actual como después de una nueva
carga de la ruta. No hubo errores en la consola del navegador. El bundle
publicado contiene `https://api.hotels-pms.com/api` como base de API (no
localhost), `/health` respondió HTTP 200 desde el host de verificación y el
preflight CORS para `https://app.hotels-pms.com` respondió HTTP 200 con los
headers de autorización esperados. `/health/datastores` mostró PostgreSQL
conectado y Redis configurado pero rechazando la conexión local. La causa raíz
del request autenticado sigue `needs-verification`: falta una traza del
provider o evidencia de la respuesta real de `/api/reports/operational/daily`
y `/api/reports/operational/alerts`.

En `/reservas` se ejecutó una mutación controlada con datos sintéticos: el
huésped rápido se creó y la interfaz asignó automáticamente el ID `13`. Sin
embargo, al seleccionar `Compartida QA Codex (#7)` y las fechas
`2026-07-20` → `2026-07-21`, el formulario publicado siguió mostrando
`Noches 0`, `Total final $ 0` y `Elegí categoría y fechas para calcular el
precio desde Tarifas.` después de más de 10 segundos. No se confirmó la
reserva ni se ejecutó ningún cobro porque el precio previo a confirmar no era
confiable. Esto es P1 del build cloud y debe repetirse después de desplegar la
rama actual; no se atribuye todavía al código local, cuya suite E2E cubre la
cotización con token vigente.

El intento de viewport explícito de 390×844 en la sesión cloud quedó en 655 px
efectivos, por lo que no se usa como certificación móvil. La suite local se
repitió desde cero con:

`E2E_PYTHON=/tmp/hpms-scale-venv-312/bin/python npm run e2e`

y terminó `47 passed (1.5m)`. Esto confirma el baseline local, pero no cierra
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
la matriz fresh de 42/42.

La corrección está validada localmente, pero el entorno web de QA debe recibir
un despliegue antes de repetir la medición allí.

El caso de fallo ahora tiene regresión E2E en
`frontend/e2e/reservation-quote-error.spec.ts` (503 del endpoint de tarifas):
la UI muestra `Total no disponible`, explica que deben revisarse fechas y
tarifas, ofrece `Reintentar` y mantiene `Crear` deshabilitado. El cambio está
en `9021c5c` y el refresh AST correspondiente en `b052ed0`. Esto mejora la
seguridad funcional del código local, pero no sustituye la repetición cloud
posterior al despliegue.

La medición cloud actual confirma que el build publicado todavía no contiene
esa experiencia de cotización: el selector de categoría y las fechas aceptan
la interacción, pero el total no se actualiza. El próximo preview debe exponer
el SHA desplegado y permitir repetir el journey con una respuesta autenticada
del endpoint de cotización.

### Reportes: error accionable y estado vacío

Se agregó una regresión E2E en `frontend/e2e/reports-error-state.spec.ts` que
simula indisponibilidad de los endpoints de reporte y alertas. La pantalla ahora
expone un `role=alert` con un mensaje comprensible, ofrece `Reintentar` y evita
mostrar `No hay datos para mostrar.` cuando la carga falló. El cambio está en
`eb6f03a`; lint, typecheck, build, el test dirigido y la suite serial 42/42
quedaron aprobados.

El entorno cloud todavía muestra el mensaje anterior `No se pudo cargar el
reporte: Failed to fetch`, porque la rama actual aún no fue desplegada allí.
La repetición provider-bound sigue siendo necesaria para separar despliegue,
proxy y backend antes de cerrar el P1.

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

### Selector de hotel y errores accionables en móvil/Analytics

Al cargar el fixture con un nombre de hotel operacionalmente largo, el smoke
WebKit reprodujo overflow horizontal en iPhone: el documento llegó a 451 px
en un viewport de 375 px y a 563 px en un viewport de 390 px. La causa era el
ancho intrínseco del selector y del banner superior, que se propagaba al
documento aunque la navegación horizontal interna fuera intencional.

Se corrigieron las restricciones `min-w-0`/`max-w-full`/`overflow-hidden`, el
salto de línea del banner y la espera determinista del fixture. Además, en
viewport móvil los controles operativos de Reservas, Caja, Stock y el banner
reciben un área mínima de 44 px; los `select` nativos requieren `height`
explícito en WebKit. La regresión móvil pasó 12/12 y la suite fresh completa
pasó 42/42 en Chromium, Chromium móvil y los tres perfiles WebKit. El cambio
todavía no está desplegado en el cloud canónico, por lo que debe repetirse allí
contra un preview autorizado.

También se agregó una regresión de UI para un `402` de Analytics: la pantalla
ahora explica que el reporte requiere el plan correspondiente, ofrece
`Reintentar` y enlaza a suscripción. El test aislado pasa 1/1. Esto mejora el
diagnóstico del frontend, pero no determina por sí solo la causa del `Failed
to fetch` observado en el cloud.

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
15, y forma parte de la suite completa 42/42. El fixture de imagen se genera con un
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

La regresión pasa en Chromium y la suite completa queda en 42/42 usando un
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
Dueño, `/reportes` se abrió en la pestaña controlada. La carga terminó en
`No se pudo cargar el reporte: Failed to fetch`; `/analytics/operations`
permaneció en `Cargando analytics...` después de aproximadamente 14 segundos.
No hubo errores ni warnings visibles en la consola del navegador. La salud
pública del API y el preflight CORS responden, pero no existe todavía una
respuesta autenticada ni traza del proveedor para aislar si el problema es
backend, proxy o consulta. Esto mantiene ambos recorridos como bloqueadores
funcionales P1 y requiere evidencia del preview/proveedor antes de corregir a
ciegas.

La ejecución fue de solo lectura: no se crearon reservas, pagos, comprobantes,
emails, webhooks ni cambios de configuración.

### Revalidación cloud adicional con navegador interno y viewport Apple

La sesión owner QA del navegador interno se reconectó y quedó autenticada en
hotel ID 4. Con viewport explícito `390×844`, la disponibilidad de Standard QA
para 2026-08-15/17 respondió `3 habitaciones`. El formulario rápido creó el
huésped sintético ID 14, pero al seleccionar la categoría y las fechas quedó
en `0 noches / $0`. La misma prueba se repitió provocando blur natural con Tab
en ambos campos de fecha, sin cambiar el resultado; no se confirmó la reserva.

La medición responsive del build cloud devolvió `557–558px` para Dashboard,
`392px` para Reservas, Stock, Reportes y Lavandería, y `390px` para Caja. En una
lectura acotada de Lavandería hubo 18 controles menores a 44px entre 47
elementos visibles, incluyendo controles de cabecera de 16–29px y controles
operativos de 37–38px. Esto mantiene un P1 cloud de Dashboard y P2 cloud en
las demás superficies móviles hasta repetir el resultado contra un SHA
provider-bound; la suite local 47/47 no reproduce ese estado con el código de
la rama.

Reportes siguió en `Cargando reporte...` después de más de 20 segundos y
Analytics/Operación en `Cargando analytics...` después de 10 segundos. Usuarios
mostró únicamente el owner; Mercado Pago no conectado y WhatsApp revocado. No
se crearon pagos, links, comprobantes, emails, webhooks, OTA, invitaciones ni
se modificó configuración. El screenshot no pudo persistirse porque el backend
de captura expiró.

La evidencia detallada quedó en
`qa/evidence/cloud-functional-sweep-20260724/README.md` y en el caso
`cloud-owner-apple-recheck-20260724` del catálogo. El SHA desplegado continúa
`needs-verification`.

La revalidación inmediata posterior confirmó el estado final de errores: después
de 10 segundos Reportes muestra `No se pudo cargar el reporte` y `No hay datos
para mostrar`; Analytics/Operación muestra `No se pudo cargar analytics.`. La
sesión siguió autenticada como owner durante ambas lecturas.

### Revalidación local posterior — Analytics exitoso y backend completo

Sobre el código funcional de `f66e22c` (con Graphify actualizado posteriormente):

- Backend: `1220 passed, 17 skipped, 12 xfailed, 1 xpassed` con Python 3.12.13.
- Frontend E2E serializado: `49 passed` en Chromium, mobile Chromium, WebKit
  iPhone SE, iPhone 15 y iPhone 15 Pro Max.
- La nueva prueba de resumen Analytics exitoso pasó en Chromium y en el
  proyecto WebKit iPhone 15 de negocio; comprueba metadata de frescura y
  ausencia de estado de error.
- Frontend: lint, `npx tsc --noEmit -p tsconfig.json` y build pasaron. El build
  mantiene sólo la advertencia no bloqueante del chunk JavaScript grande.

El `pytest` invocado con `.venv/bin/python` no pudo importar el proyecto porque
ese entorno local usa Python anterior a 3.10; la ejecución válida se repitió con
el intérprete Python 3.12.13 que utiliza E2E y completó la suite sin fallas.

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
- La UI de analítica fue validada por build, contrato de error y contratos API,
  pero todavía no se repitió el journey completo contra un preview
  provider-bound.
- El warehouse local incluye replay acotado cada cinco minutos y reconciliación
  nocturna sobre PostgreSQL. Esto no prueba ClickPipes CDC ni el lag del
  proveedor: esas mediciones siguen pendientes en un preview aislado.
- Las pruebas que mutan la SQLite local deben ejecutarse serializadas. La
  corrida paralela de cinco proyectos reprodujo `database is locked` durante
  un cobro; una corrida secuencial con `--workers=1` pasa 42/42. Una corrida
  paralela que arranque dos servidores E2E sobre el mismo archivo también puede
  fallar durante el reset con `table users already exists`; no es evidencia de
  un fallo funcional del PMS, pero sí una limitación del arnés local.

## Próximo gate

Provisionar el preview aislado con sus proveedores, repetir el smoke web/móvil
y el recorrido de negocio con datos de prueba aislados. Recién después ejecutar
las pruebas de carga/concurrencia y el gate de release; no usar el manifiesto de
ejemplo como evidencia de despliegue.

### Revalidación local posterior — Ficha de huésped y acompañantes

Se agregó el journey guest-companion-journey.spec.ts para cubrir desde la
interfaz la creación rápida de un huésped, su búsqueda por apellido y el alta de
un acompañante con documento y relación. Pasó en Chromium y en WebKit iPhone 15.
La prueba usa datos sintéticos con sufijo temporal y no ejecuta pagos, emails,
webhooks ni integraciones externas. La regresión E2E quedó en 50/50 sobre el
commit 0510fa0.

También se agregó el journey zz-cash-control-journey.spec.ts para cubrir
ingreso y egreso manual, cierre con diferencia, aprobación, custodia automática
del owner y caja sucesora. Pasó en Chromium y en WebKit iPhone 15; la suite
completa volvió a pasar 51/51 sobre el commit b5d1a6d.

### Revalidación local posterior — Consumos y cargos adicionales

Se agregó `frontend/e2e/reservation-charge-journey.spec.ts` para cubrir el
faltante funcional de cargar minibar, desayuno u otros extras desde la Ficha de
la estadía. El backend persiste el cargo como `BillingAdjustment`, actualiza el
saldo operativo derivado del ledger, audita el actor y restringe la acción a
reservas activas con permiso `reservation:charge`. La pantalla usa descripción e
importe comprensibles, muestra el saldo actualizado y conserva el cargo al
cerrar y reabrir la Ficha.

La primera corrida E2E detectó que la migración original almacenaba los nombres
de miembros (`CHARGE`) mientras el modelo persistía los valores (`charge`). Se
agregó `20260724_billing_adjustment_enum_values` para reparar SQLite y PostgreSQL
sin quitar la restricción. La prueba focalizada pasó 1/1 en Chromium y 1/1 en
WebKit iPhone 15; las pruebas backend relacionadas pasaron 13/13 y la regresión
local serial fresh pasó 52/52 sobre el commit `9aa8dad`. La regresión backend
completa posterior pasó 1223/1223 (con 17 skips, 12 xfails y 1 xpass). No se ejecutaron pagos,
emails, webhooks, OTA ni integraciones externas.

### Revalidación serial del estado actual — commit `c8e1034`

Para evitar la carrera conocida de la SQLite compartida, se ejecutaron las
matrices en dos procesos separados:

- `E2E_PYTHON=/tmp/hpms-scale-venv-312/bin/python E2E_WEBKIT_BUSINESS=false npm run e2e`: **52/52** aprobados en Chromium, mobile Chromium, WebKit iPhone SE, iPhone 15 e iPhone 15 Pro Max.
- `E2E_PYTHON=/tmp/hpms-scale-venv-312/bin/python E2E_WEBKIT_BUSINESS=true npm run e2e -- --project=webkit-iphone-15-business --workers=1`: **10/10** aprobados, incluyendo reservas, inventario, estadía, lavandería, reportes, comprobantes, cargos y caja.
- La tentativa de activar ambos grupos en una sola corrida terminó 59/62: tres tests quedaron bloqueados por dos proyectos mutando/reseteando `_e2e.db` al mismo tiempo. El fallo se reproduce sólo con esa combinación concurrente y no reaparece en las dos corridas seriales; queda como limitación del arnés, no como aprobación de una ejecución paralela.

Esta evidencia confirma el estado local de la rama actual, pero no cambia el
gate cloud: el artefacto publicado sigue sin un `code_sha` provider-bound y la
matriz visible de cinco personas todavía no puede cerrarse.

### Revalidación local — registro y onboarding en Apple WebKit

El proyecto `webkit-iphone-15-business` excluía por configuración el journey
de registro y onboarding, por lo que el intento inicial no descubría pruebas.
Se agregó `auth-onboarding-journey.spec.ts` a ese proyecto y el recorrido pasó
1/1 en WebKit iPhone 15: registro de owner sintético, verificación mediante el
outbox local, hotel/categoría/habitación, política y pagos, alta de staff,
cierre de sesión, recuperación de contraseña e inicio de sesión final.

La matriz WebKit serial completa pasó posteriormente 11/11. Durante una primera
corrida ampliada la aserción E2E de stock agotó su espera tras registrar un
ingreso; el snapshot final mostraba correctamente `10 unidad`. La reproducción
acotada onboarding+negocio (5/5) y la repetición completa (11/11) no repitieron
el evento, por lo que queda como observación P3 del arnés/caché local y no como
defecto funcional confirmado. No se usaron credenciales, correo, pagos,
webhooks ni OTA externos.

### Revalidación local — contratos de pagos e integraciones sin side effects

Se ejecutó con Python 3.12.13 la regresión focalizada de links de pago,
comprobantes, idempotencia, webhooks Mercado Pago, booking público, WhatsApp y
email saliente usando fixtures y adaptadores mock:

```text
40 passed in 3.42s
```

La suite comprobó creación/listado/cancelación de links, tolerancia a fallas del
gateway, entrega mock, firma e idempotencia de webhooks, aislamiento por hotel,
flujo de comprobante rechazado/reintentado/aprobado, sobrepago e idempotencia de
pagos, además de los contratos público y WhatsApp. La regresión visual/operativa
relacionada pasó en Chromium y WebKit iPhone 15. No se usaron credenciales,
Mercado Pago, Gmail, webhooks, WhatsApp ni dinero reales.

El resultado no cierra el gate cloud: el artefacto publicado sigue sin SHA
provider-bound y los P1 de disponibilidad, cotización, Reportes y Analytics
siguen pendientes de repetición contra un preview aislado.

### Revalidación local — navegación operacional por rol en Apple WebKit

La matriz WebKit de negocio no incluía `role-journey.spec.ts` y ese test sólo
interactuaba con el `aside` de escritorio. En iPhone, la aplicación expone la
superficie operativa mediante `nav[aria-label="Navegación móvil"]`, por lo que la
primera ejecución agotó el timeout intentando pulsar un enlace de escritorio
oculto. No era un fallo confirmado de autorización: la sesión de manager y el
enlace a Reportes estaban visibles en la navegación móvil.

Se actualizó el journey para elegir la navegación visible del dispositivo,
comprobar la ausencia de enlaces prohibidos y abrir la tarea permitida. Manager
alcanzó Reportes, Recepción alcanzó Caja y Housekeeping alcanzó Lavandería:
**3/3** en WebKit iPhone 15. La regresión serial de ese proyecto, incluyendo
onboarding, reservas, pagos, inventario, caja y estos roles, terminó **14/14**
en el commit `70c40d4`.

No se modificaron permisos de producto, se usaron las personas sintéticas
seedadas y no se ejecutó correo, pago, webhook ni integración externa. Esta
evidencia sigue siendo local: no sustituye las cinco sesiones reales ni el
preview cloud aislado que el gate funcional exige.

### Revalidación local — matriz funcional Apple WebKit completa

La configuración dejaba el recorrido de negocio completo sólo en iPhone 15;
iPhone SE e iPhone 15 Pro Max ejecutaban únicamente el smoke responsive. Se
extrajo la lista de journeys críticos en una sola configuración y se añadieron
dos proyectos WebKit de negocio adicionales, siempre con `--workers=1` para no
compartir mutaciones sobre la SQLite E2E.

Los tres tamaños Apple completaron el mismo recorrido, sin acciones externas:

- iPhone SE: **14/14**.
- iPhone 15: **14/14**.
- iPhone 15 Pro Max: **14/14**.

El total es **42/42**. Incluye registro/onboarding/recuperación, reserva,
cotización y conflicto, comprobantes y pagos mixtos simulados, estadía,
inventario, caja, reportes, analytics, y las rutas permitidas de manager,
recepción y housekeeping. La emulación usa WebKit de Playwright; la
certificación en Safari nativo o en un dispositivo físico sigue pendiente.

### Revalidación local — tarifas por método de pago en Apple WebKit

El calendario de tarifas tenía prueba de interfaz con adaptador API aislado,
pero no formaba parte de la matriz WebKit de negocio. Se incorporó para que los
tres tamaños Apple comprueben la edición de precio base, efectivo y
transferencia, la validación de importes vacíos, cambios masivos por días de la
semana y el estado de mapeo de canales.

Cada tamaño aprobó **15/15** escenarios, para un total de **45/45**. El caso de
tarifas usa fixtures/mock locales y, por tanto, demuestra la UX y el contrato
del editor, no la propagación a un proveedor OTA. La integridad del cálculo de
reservas y precios diarios sigue cubierta además por los tests de servicio y
los journeys de reserva locales.

### P1 corregido — master-admin usable en Apple WebKit

Al incluir el quinto rol requerido en la matriz Apple, el primer recorrido de
master-admin detectó un defecto funcional P1: en móvil el panel ocultaba todo
el menú de navegación y el dashboard podía exceder el ancho del viewport. Por
eso Billing Policy y Audit Log eran inalcanzables para ese rol desde un iPhone.

La corrección agrega una navegación móvil horizontal con objetivos táctiles de
al menos 44 px, permite que el contenedor principal se reduzca (`min-w-0`) y
trunca el email largo. El journey ahora exige que la navegación sea visible,
que `document.documentElement.scrollWidth` no supere el viewport y que Billing
y Audit sean navegables desde la superficie visible.

Master-admin aprobó **2/2** en iPhone SE, iPhone 15 e iPhone 15 Pro Max. La
regresión total posterior aprobó **17/17 por dispositivo (51/51)**, con lint,
typecheck y build en verde. No se usaron proveedores, email, Stripe ni acciones
de plataforma externas. La E2E base completa de Chromium y smoke móvil también
se reejecutó y aprobó **52/52**.

### Revalidación cloud visible — P1 aún presente

Con la sesión QA ya abierta en el navegador interno se volvió a comprobar la
instancia publicada, sin crear reservas ni ejecutar pagos, emails, webhooks,
OTA o invitaciones. Analytics/Operación terminó en **“No se pudo cargar
analytics.”** y Reportes terminó en **“No se pudo cargar el reporte: Failed to
fetch”** junto con el estado vacío. En Reservas, la consulta de disponibilidad
para la categoría de prueba y el rango 2026-08-15 a 2026-08-17 devolvió tres
habitaciones, pero los campos se restablecieron a 2026-07-24/25; por lo tanto
el resultado no corresponde al rango solicitado y no permite confiar en una
cotización posterior.

También se comprobó el layout de Reservas a 390x844: el documento midió 392px
de ancho y se detectaron objetivos interactivos por debajo de 44px. Esta
observación refuerza el P1 móvil de la instancia publicada. No se asigna al
commit local actual porque el despliegue no expone un `code_sha`
provider-bound; debe corregirse y verificarse en un preview aislado antes de
cerrar la puerta funcional.

### Continuación cloud sobre el Preview existente — Reportes, Analytics, Caja y Stock

El Preview de `codex/feature/pms-e2e-scale-hardening` quedó ligado al commit
`3a6ebda`. Se usaron exclusivamente el proyecto Vercel, API y base de datos
existentes; no se creó un proyecto Supabase, Render ni proveedor de pagos
adicional. La migración ya versionada que agrega `pre_check_in` al enum de
reservas se aplicó de forma aditiva al entorno existente, corrigiendo el error
de Reportes. La pantalla volvió a cargar sus secciones operativas con datos.

También se corrigió un crash P1 de Analytics/Operación: el backend existente
podía omitir `data_source` y la UI invocaba `trim()` sobre `undefined`. El
frontend acepta ahora metadata heredada, usa PostgreSQL como fallback visible y
la regresión específica aprobó 2/2. La revalidación cloud del Preview mostró
Analytics/Operación con métricas y el estado `Datos PostgreSQL, al día`, sin
errores de consola.

Como recorrido funcional real se abrió una caja QA con saldo inicial cero,
se registró un ingreso manual sintético y un egreso equivalente, y se cerró con
saldo contado y esperado en cero. No se asociaron reservas, no se ejecutaron
pagos, links, emails, webhooks ni OTAs. En Stock, el flujo ofrece acciones de
ingreso/egreso/ajuste, búsqueda de reserva por huésped o código, resultado
previsto y bloqueo visible de egresos que dejarían stock negativo. Los saldos
negativos visibles corresponden a datos QA históricos; el servicio y la UI
actuales bloquean nuevos egresos negativos.

La automatización del navegador interno no confirma el evento nativo de los
campos `date`, por lo que reinyecta el valor controlado al solicitar
disponibilidad. No se atribuyó ese efecto a producto: el escenario de
preservación de rango aprobó 2/2 en Chromium y 2/2 en WebKit iPhone 15. El
smoke responsivo vigente aprobó 12/12 entre iPhone SE, iPhone 15 e iPhone 15
Pro Max. La certificación final en Safari nativo o dispositivo físico sigue
pendiente, al igual que los pagos reales; ambos quedan fuera de esta ejecución
para evitar efectos externos.

Validación posterior al cambio: `analytics-success` Chromium 2/2,
`reservation-lifecycle` Chromium 2/2 y WebKit iPhone 15 2/2, servicio de
Stock 4/4, regresión E2E Chromium 37/37, journey de negocio WebKit iPhone 15
18/18 y smoke Apple WebKit 12/12. Persisten warnings de cache/lock degradado
del arnés local y warnings de serialización de Decimal; no hubo fallos
funcionales en esas corridas.

### P1 corregido — webhooks Mercado Pago sin secreto deben fallar cerrados

La revisión manual de pagos detectó que las dos rutas públicas de webhook de
Mercado Pago reutilizaban un validador que retornaba sin error cuando el
secreto no estaba configurado. En esa condición un request podía avanzar hasta
la resolución de la referencia de pago, en vez de ser rechazado antes de tocar
el flujo financiero.

Se añadió primero una prueba de regresión que falló al no recibir la excepción
esperada. La corrección ahora rechaza explícitamente el webhook no configurado
antes de validar headers, resolver referencias o crear movimientos. Las rutas
de link de pago y de prueba usan el mismo validador, por lo que ambas quedan
cubiertas. No se envió ningún webhook, pago o credencial real.

Validación focal posterior: 16 pruebas de links, API, webhook e integridad de
rutas aprobadas. La revisión ampliada de auth, aislamiento entre hoteles,
webhooks, preview sin efectos externos, API keys y master-admin aprobó 132
pruebas; el bloque específico de runtime, RLS, comprobantes, webhooks y rate
limit aprobó 36. El fix está en el commit `7278b2c` de la rama de trabajo.

### Regresión integral posterior a la corrección de seguridad

La rama `7278b2c` aprobó nuevamente la puerta local completa:

- Backend: **1223 passed, 17 skipped, 12 xfailed, 1 xpassed**.
- Frontend: lint, typecheck y build aprobados. Persiste el warning conocido
  de bundle de aproximadamente 793 kB, sin error de compilación.
- Migraciones: `alembic upgrade head` sobre SQLite virgen aprobado.
- E2E escritorio: **37/37** en Chromium.
- E2E operativo Apple: **18/18** en WebKit iPhone 15.

El Preview Vercel incorpora el cambio de interfaz móvil `8dfaf35` y se
revalidó a 390 px: selector de hotel, rol, Aplicar y cerrar sesión miden 44 px
sin overflow horizontal. El nuevo fix de webhook es de backend: está probado
en la rama, pero no se declara desplegado en la API existente hasta que se
ejecute su ciclo de despliegue explícito.

La puerta de release confiable sigue sin aprobarse: el verificador encontró
cero artefactos QA firmados y el contrato del repositorio exige un Preview con
infraestructura aislada. Esta ejecución respetó la instrucción operativa de
usar sólo el entorno existente, por lo que no se creó Supabase, Render ni
servicio adicional y no se fabricó evidencia equivalente. La certificación
Safari nativa/dispositivo físico y la prueba de pago real siguen pendientes
por las exclusiones de efectos externos.

### P1 corregido — exportación de huéspedes y snapshots de auditoría sin PII

La auditoría de seguridad detectó que el CSV de libro de huéspedes contenía
datos identificatorios y dependía solamente de una sesión hotel-scoped. También
detectó que los snapshots de `guests` y `guest_companions` persistían toda la
fila en `audit_logs` y podían proyectarse a Mongo.

El commit `d260449` agrega el permiso explícito `guest:export`: owner,
co-owner y manager lo tienen por defecto; recepción y housekeeping quedan
denegados salvo override hotel-scoped. El endpoint de exportación ahora usa el
guard existente y no devuelve CSV cuando responde 403. Los snapshots de huésped
y acompañante se reducen a contexto operativo permitido; la misma
normalización se aplica en la escritura directa, el decorador y la proyección
de auditoría. No se procesaron datos de clientes, sesiones ni proveedores
externos durante la validación.

La prueba se escribió roja: recepción podía recibir HTTP 200 con el CSV y no
existía `guest:export`. Posteriormente aprobaron 29 pruebas focales de
permisos, exportación, auditoría y proyección Mongo; la regresión backend
completa terminó en **1233 passed, 17 skipped, 12 xfailed, 1 xpassed**. Esto
reduce una exposición local de PII, pero no sustituye el drill de backup/restore
ni la evidencia cloud firmada.

### P1 corregido — las rutas privadas del Preview no deben redirigir a producción

El Preview de Vercel de la rama de trabajo identificaba sólo el host canónico
de producción como aplicación. Por eso abrir `/login` en un dominio Preview
trataba el Preview como sitio público y redirigía la ruta privada a producción,
impidiendo hacer QA provider-bound del commit a revisar.

El commit `121ec1a` agrega una excepción explícita, desactivada por defecto y
limitada mediante variables de entorno de Preview, para los sufijos de host
permitidos. La suite contiene una regresión independiente: antes del cambio
el navegador terminaba en el host equivocado; después, el test quedó verde
**1/1** y la pantalla de login permaneció en el dominio Preview. La variable
se creó únicamente con alcance Preview; no se cambiaron Render, Supabase,
producción ni ningún proveedor externo.

Como validación posterior, el owner QA inició sesión en el Preview y cargó
`/reservas`, `/tarifas`, `/caja` y `/operacion/stock` contra el entorno
existente, sin pagos, emails, webhooks, OTA, ni mutaciones externas. También
aprobaron la regresión completa **37/37** en Chromium y **18/18** para el
journey operativo en WebKit iPhone 15. La primera autenticación completó, pero
tardó aproximadamente un minuto: se clasifica como **P2 de performance** del
arranque del backend y queda pendiente diagnosticarlo con telemetría del
provider. No es evidencia de un fallo de credenciales ni de routing.

El barrido read-only posterior cargó otras diez rutas de operación y
configuración del owner sin error visible. Reportes y Analytics/Operación se
verificaron por separado, esperando su carga asíncrona, y ambos terminaron sin
error ni estado vacío. Para la superficie Apple, el smoke responsivo WebKit
volvió a aprobar **12/12** entre iPhone SE, iPhone 15 e iPhone 15 Pro Max. El
navegador interno no dispara de forma fiable los eventos nativos de los campos
`date` controlados, por lo que no se usa para descalificar la cotización cloud:
esa interacción sigue cubierta por las pruebas Chromium y WebKit ya aprobadas.

### P2 mitigado — el login lento ahora informa progreso

La primera autenticación del Preview completó pero quedó cerca de un minuto en
`Conectando...` mientras el backend existente arrancaba. El tiempo de respuesta
de proveedor requiere telemetría y no se oculta como resuelto; sin embargo, el
operador ya no queda sin explicación durante la espera.

El commit `900c866` muestra un estado accesible después de cinco segundos,
indicando que la conexión está demorando y que los datos de acceso continúan
en curso. Una regresión E2E mantiene `/api/auth/login` pendiente, verifica el
mensaje y luego libera una respuesta de error. La prueba fue roja antes del
cambio y verde después. La revalidación posterior aprobó lint, typecheck,
build, **38/38** E2E Chromium y **18/18** journeys operativos WebKit iPhone
15. No se cambiaron credenciales, políticas de autenticación ni proveedores.

### Revalidación owner del Preview existente — 2026-07-25

Se abrió nuevamente el Preview Vercel de la rama de trabajo y la ruta privada
`/login` permaneció en ese host. La sesión owner QA se autenticó y cargó el
dashboard sin error visible. En modo sólo lectura, Reportes terminó con el
reporte diario y su estado de caja, y Analytics/Operación mostró sus métricas
y la procedencia PostgreSQL.

La consulta de disponibilidad del Preview sigue sin poder certificarse por el
navegador interno: este puente actualiza el valor visible de los controles
nativos `date`, pero no propaga de manera fiable su evento a React antes de la
consulta; al re-renderizar vuelve al valor controlado inicial. No se clasifica
como defecto de producto porque el mismo contrato de preservación de rango
aprobó en Chromium y WebKit iPhone 15. No se creó ninguna reserva, cobro,
link, comprobante, email, webhook, OTA ni invitación.

Esta lectura demuestra el comportamiento visible del Preview contra el
entorno existente, no una procedencia provider-bound: Vercel no expone en esta
ejecución un SHA verificable del backend ni existe la evidencia firmada
requerida por la puerta de release. La matriz real de manager, recepción,
housekeeping y master-admin, Safari nativo/dispositivo y las operaciones
mutantes siguen pendientes.

### P2 corregido — navegación móvil con objetivos táctiles de 44 px

El audit visual del Preview a 390×844 detectó 28 enlaces de la navegación
móvil con sólo 24 px de alto, además del acceso de inicio de 36 px. La prueba
de regresión se agregó antes del cambio y falló con todos los enlaces listados
como objetivos insuficientes.

El commit `8f1d14d` convierte el acceso de inicio y cada enlace del carrusel
de navegación móvil en controles de al menos 44 px, sin modificar sus rutas ni
permisos. La prueba focal aprobó en Chromium móvil, WebKit iPhone SE, iPhone
15 e iPhone 15 Pro Max; lint, typecheck y build también aprobaron. Tras
publicar la rama, el Preview a 390 px mostró los 28 enlaces y el acceso de
inicio a 44 px o más, sin overflow horizontal ni errores visibles. No hubo
mutaciones de negocio ni efectos externos.

### P1 corregido — cierre de caja contra el entorno existente

El recorrido owner del Preview existente abrió una caja QA equilibrada con un
ingreso y un egreso sintéticos y encontró dos fallos reales al cerrarla. Sin
Redis, el bloqueo distribuido obligatorio impedía cerrar la caja; el commit
`8e0f9e5` añade el lock transaccional advisory de PostgreSQL como fallback. Al
resolver ese bloqueo, el backend reveló que el entorno existente tenía el
historial de Alembic atrasado respecto de tablas ya presentes: faltaban la
referencia sucesora y la tabla de custodia de caja.

Los commits `ace7f4c`, `b1e1bd0` y `15fdb88` agregan una reparación de
arranque PostgreSQL-only, aditiva, idempotente y transaccional. Crea solamente
la referencia de sucesión, las restricciones multi-tenant y, si no existe, la
tabla de custodia con su enum, índice y RLS. No reejecuta el árbol completo de
migraciones ni modifica movimientos de negocio. El intento de `alembic upgrade
head` se mantuvo fuera del arranque porque intenta recrear tablas ya existentes
en este entorno; reconciliar ese marcador de historial sigue siendo un riesgo
P1 separado.

Después de desplegar `15fdb88` en el Render existente y redeplegar el Preview
de esta rama con `VITE_API_URL` apuntando a la API canónica existente, el cierre
QA devolvió `Caja cerrada.` y creó automáticamente una caja sucesora abierta.
No se usaron dinero real, links de pago, comprobantes, emails, webhooks ni
OTAs. La regresión backend posterior aprobó **1239 passed, 17 skipped,
12 xfailed, 1 xpassed**. Esta evidencia valida el flujo cloud de caja para el
owner QA, pero no sustituye la auditoría completa de drift de Alembic ni la
evidencia firmada de la puerta de release.

### P2 corregido — aprobación de diferencia de caja usable en móvil

La inspección del Preview existente a 390×844 confirmó que Stock no presenta
overflow y sus controles visibles alcanzan 44 px; Caja tampoco presenta
overflow, pero el checkbox `Aprobar diferencia al cerrar` medía 13 px. Era un
riesgo de interacción para una confirmación financiera en teléfono.

El commit `8b6cb4d` hace que el checkbox de aprobación mida 44×44 px y añade
una regresión específica. La prueba fue roja en WebKit iPhone 15 con 12 px y
verde tras el cambio: el smoke mobile completo aprobó 5/5. Después de publicar
la rama, el Preview existente volvió a medir 44×44 px a 390×844 y sin overflow
horizontal. No se creó un movimiento adicional durante esta comprobación.

No hay Xcode Simulator instalado en este equipo, por lo que la certificación
manual en Safari nativo o dispositivo físico sigue pendiente. La evidencia
actual cubre WebKit Playwright y el viewport cloud del navegador interno.

### P1 corregido — configuración de medios de pago guardable

En el Preview existente, habilitar Transferencia desde Configuración/Hotel no
persistía. La causa no era autorización ni API: el formulario de configuración
también contenía los borradores de alta de categoría y habitación; uno de esos
campos tenía un mínimo numérico inválido por defecto y el navegador bloqueaba
silenciosamente el submit de configuración.

El commit `4529a78` hace que el botón `Guardar cambios` omita la validación
nativa de los borradores no enviados, manteniendo las validaciones de sus
acciones de alta. La regresión E2E fue roja antes del cambio y verde después:
el owner habilita Transferencia, guarda y la opción permanece activa tras
recargar. En el Preview cloud, el mismo recorrido mostró `Cambios guardados.`
y la opción siguió habilitada tras la recarga. Esto también dejó visible el
formulario de comprobante de transferencia sobre una reserva QA pendiente.

El Render existente arrancó el commit `9d6d084` y su chequeo de drift informó
que no faltan tablas de modelos; por lo tanto, `payment_proofs` y
`payment_proof_blobs` ya están disponibles con sus restricciones y RLS. El
selector nativo de archivos no está expuesto por el puente del navegador
interno de Codex, así que la carga cloud de una imagen sintética y su
aprobación quedan pendientes de un navegador/dispositivo con selector de
archivos. El journey completo de reintento, rechazo y aprobación continúa
cubierto localmente en Chromium y WebKit con imágenes sintéticas; no se
transfirió dinero, no se usaron comprobantes reales y no se llamó a proveedores
externos.

### P1 corregido — inventario con historial operativo auditable

El flujo cloud de inventario guiaba correctamente ingresos, egresos, ajustes y
el bloqueo de stock negativo, pero no exponía al operador el historial de los
movimientos ya persistidos. Eso impedía revisar rápidamente el motivo, la
cantidad y el contexto de un egreso, que es esencial para la operación diaria.

El commit `e32ded9` incorpora un endpoint hotel-scoped, limitado y ordenado por
recencia, junto con un historial visible en Stock. La interfaz muestra nombres
operativos de artículo y ubicación, código de reserva cuando corresponde,
cantidad, fecha y motivo; nunca muestra IDs internos. La prueba se escribió
roja por la ausencia del endpoint y luego aprobó tanto el servicio/API como el
journey de UI. La regresión backend completa terminó en **1242 passed, 17
skipped, 12 xfailed y 1 xpassed**; lint, typecheck, build y el E2E focal de
stock también aprobaron.

En el Preview existente, con la API y base de datos actuales, se registró un
ingreso QA y un egreso QA sintéticos, se verificó el bloqueo del intento que
dejaba el saldo negativo y luego se confirmó que ambos aparecen en el historial
con sus motivos. Al elegir el artículo, el historial quedó filtrado sólo a sus
movimientos. En 390×844 no hubo overflow horizontal y el historial permaneció
visible. Render desplegó el commit y su health check quedó Live; Vercel publicó
el Preview Ready. No se usaron dinero real, pagos, emails, webhooks, OTA ni
datos de huéspedes.

### P1 corregido — check-in guía primero al cobro pendiente

En el listado de reservas, el botón Check-in se habilitaba para reservas
pendientes o con seña aun cuando el backend sólo admite `fully_paid` o
`pre_check_in`. El operador encontraba así una acción que terminaba en un
rechazo técnico, en vez de recibir el paso operativo necesario para completar
la estadía.

El commit `2b36070` alinea el contrato visible con el backend: al iniciar un
check-in con saldo pendiente abre la ficha de pago y explica que debe cobrarse
el saldo con `Pago total`, que queda registrado en caja. Una reserva pagada o
en pre check-in sí ejecuta el check-in. También se incorpora el estado
`pre_check_in` al contrato TypeScript, etiquetas, filtros y badges, para que
no quede oculto ni degradado a texto técnico.

La regresión fue roja antes de la corrección y verde después en el journey de
reserva Chromium y WebKit iPhone 15. Lint, typecheck y build aprobaron. En el
Preview existente, una reserva QA pendiente abrió el cobro con la guía visible
sin devolver el error técnico; una reserva QA pagada pasó a Check-in y luego a
Check-out. En 390×844 el botón de check-in midió 69×44 px y la página no tuvo
overflow horizontal. No se realizaron pagos, links, emails, webhooks, OTA ni
acciones sobre datos de huéspedes reales.
