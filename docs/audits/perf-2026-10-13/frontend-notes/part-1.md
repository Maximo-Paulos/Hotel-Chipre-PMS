# Auditoría de consumo — frontend, parte 1: dominio de reservas

Fecha de lectura: 2026-10-14. Rutas relativas a `/home/user/Hotel-Chipre-PMS/frontend` salvo que diga `app/` (backend).
Archivos leídos COMPLETOS con Read en tramos de 700 líneas o menos (8 archivos, 11.060 líneas):

| Archivo | LOC | Lecturas |
|---|---|---|
| `src/views/protected/ReservationsPage.tsx` | 6.120 | 9 tramos (1-700 … 5601-6120) |
| `src/components/ReservationDetailDrawer.tsx` | 1.949 | 3 tramos |
| `src/api/reservations.ts` | 757 | 2 tramos |
| `src/components/ManualOtaReservationModal.tsx` | 548 | 1 |
| `src/components/GuestQuickCreatePanel.tsx` | 514 | 1 |
| `src/components/OccupancyGrid.tsx` | 452 | 1 |
| `src/hooks/useReservations.ts` | 384 | 1 |
| `src/views/protected/OccupancyPlanningPage.tsx` | 336 | 1 |

Para verificar afirmaciones leí además (solo lectura, fragmentos): `src/main.tsx`, `src/api/client.ts` (tramos), `src/api/queryInvalidation.ts`, `src/api/queryKeys.ts`, `src/api/queryPolicy.ts`, `src/utils/date.ts`, `src/utils/reservationStatus.ts`, `src/utils/roomMove.ts`, `src/utils/escapeHtml.ts`, `src/hooks/{useGuardedMutation,usePayments,useRooms,useCategories,useGuests,useGuestRestrictions,useHotelConfig,useSubscription,useDialogA11y,useReservationDrawer,useCollaborativeResource}.ts`, `src/components/{GuestRestrictionBadge,ReservationGlobalSearch}.tsx`, `src/ui/AppShell.tsx` (tramos), `src/i18n.ts`, y en backend `app/api/{reservations,payments,checkin,companies,room_movement_groups,reservation_groups,payment_proofs,guests}.py`, `app/services/reservation_service.py`, `app/services/permission_service.py`, `app/schemas/{reservation,payment_proof}.py`.

Convenciones: [P0] pérdida de datos/seguridad/caída · [P1] impacto alto en consumo o correctitud · [P2] mejora menor · [info]. "(verificado: archivo:línea)" = visto en el código; "(inferido, no verificado)" = deducción. Cifras "estimado" indican de dónde salen.

---

## 1. Requests de montaje por pantalla

Datos globales verificados: `QueryClient` con `staleTime: 30_000`, `refetchOnWindowFocus: false`, 1 reintento solo para errores de red/5xx (`src/main.tsx:17-30`). No existe ningún `refetchInterval` en todo `frontend/src` (grep vacío). Los listados de reservas, acciones pendientes y habitaciones usan `staleTime` de 5 min (`src/api/queryPolicy.ts:7`) y dependen de eventos de dominio en tiempo real para invalidarse.

### 1.1 `/reservas` (ReservationsPage) — al montar, sin interacción
Requests propios (7), todos en paralelo, sin cascada:
1. `GET /api/reservations/?order=check_in&limit=200` (`ReservationsPage.tsx:403-417`; `useReservations.ts:69-84`).
2. `GET /api/reservations/actions/pending?limit=12` (`:418`; key distinta de la del Dashboard, que usa `limit=8`, `DashboardPage.tsx:90`).
3. `GET /api/rooms/` (todas las habitaciones, sin paginar) (`:419`; `useRooms.ts:15-20`).
4. `GET` categorías (una sola request: `useRooms().categoriesQuery` y `useCategories()` comparten key `room-categories`) (`:419-420`; `useRooms.ts:22-27`, `useCategories.ts`).
5. `GET /api/companies/options` (`:421-426`). En planes por debajo de "pro" el backend responde 402 (ver hallazgo en este archivo).
6. `GET /api/reservation-groups?limit=6` (`:435-440`; `api/reservations.ts:436-442`).
7. `GET /api/room-movement-groups/?limit=6` (`:572-577`; `api/allocationRuns.ts:54-55`), sin gate de permiso (el backend exige `reservation:move`).
Compartidas con AppShell (no suman): hotel-config (solo si `hotel_settings:read`), subscription (solo si `settings:subscription:view`).
Deshabilitadas hasta una acción (no se disparan): detalle (`useReservation`, `usePaymentSummary`, `operations-summary`, comunicaciones, auditoría, `useGuest`), cajas, recargos, FX, cotización, disponibilidad del form.
Observadores de query en el mismo componente: 25 sitios de llamada (`grep` en líneas 389-1802), 26 observadores contando que `useRooms` abre 2.

### 1.2 `/reservas` — abrir "Editar" (`openEdit`)
`payment-summary` (cash:operate), `guest/{id}`, `payment-links`, `payment-proofs` (si hay permisos; solo se usa dentro del bloque "transferencia", `:4763-4863`), `cash-sessions` (cash:view y form abierto), `payment-surcharges` (cash:operate y form abierto), `POST /api/collaboration/tickets` + WebSocket (`useCollaborativeResource`, enabled solo si `formOpen && editing`, `:578-595`), `GET fx quote` solo si la moneda recibida difiere. Total 6-7 requests + 1 WebSocket. Guardar = PATCH + refetch de lista (200 filas) + acciones pendientes (+ planilla si está montada).

### 1.3 `/reservas` — abrir "Nueva" y completar
Sin requests hasta elegir categoría+fechas. Luego: `GET /api/rooms/availability` (key por categoría+fechas, `:775-793`) y `GET /api/bookings/price-quote` (key incluye categoría, fechas, método de precio, ocupación, company_id y guest_id, `useReservations.ts:114-137`). Cada cambio de adultos/niños, empresa o huésped dispara otra cotización (sin debounce). Buscar huésped: 1 request por término (debounce 300 ms) + hasta 8 `guest-restrictions` (ver GuestQuickCreatePanel).

### 1.4 `/reservas` — "Ficha" (modal propio, `openDetails`)
`GET /api/reservations/{id}`, `payment-summary`, `operations-summary`, comunicaciones, auditoría (si `operations:audit:view`), `guest/{id}` = 5-6 requests en paralelo (`:505-523`, `:1802`). El `guest_id` sale de la lista (`reservations.find`, `:506-507`), así que no hay cascada. Es una segunda UI de detalle, distinta del Drawer global.

### 1.5 Drawer global `?reserva=<id>` (ReservationDetailDrawer, montado en AppShell)
Etapa 1 (paralelo): `reservation/{id}` + `operations-summary` + `payment-summary` (`:257-262`).
Etapa 2 (cascada, dependen de `reservationQuery.data`): `guest/{guest_id}` y `GET /api/checkin/validate/{guest_id}` (staleTime 0) cuando el estado es pre-llegada (`:323-328`), `guest-restrictions` (el badge se monta recién con la reserva, `:959-961`), y si hay `company_id`: noches de empresa, documentos de empresa y tarifas nocturnas (`:271`, `:293`, `:297-300`).
Total: 3 (etapa 1) + 3 a 7 (etapa 2). La reserva ya estaba cargada en la lista o en la planilla pero no se siembra la caché (`setQueryData`/`initialData`), por eso hay cascada.

### 1.6 `/operacion/planilla` (OccupancyPlanningPage)
5 requests: `GET /api/reservations/occupancy-grid` (ventana de 14 días), 2 prefetch (ventana anterior y siguiente), `GET /api/rooms/`, categorías (`OccupancyPlanningPage.tsx:37-43,121-126`). Cada respuesta repite el arreglo `rooms` completo. Al navegar de ventana se repiten los 2 prefetch.

### 1.7 Otras pantallas que consumen estos hooks (referencia cruzada)
- Header global (`ReservationGlobalSearch`, en AppShell): `useReservations({ search })` sin debounce, 1 request por tecla desde 2 caracteres (`ReservationGlobalSearch.tsx:22-24,33-38`).
- `RoomsPage.tsx:91`: `useOccupancyGrid(hoy, hoy+92 días)`, la ventana máxima que acepta el backend (`app/api/reservations.py:772-773`).
- `StockPage.tsx:203`: `listReservations({ status:"all", order:"check_in", limit:200 })`, mismo problema de "200 más antiguas".

---

## 2. Notas por archivo

- `src/views/protected/ReservationsPage.tsx` (6.120) — Página monolítica de reservas: KPIs, acciones pendientes, calendario de ocupación, filtros, disponibilidad, reasignación automática, grupos, lista (tabla + tarjetas), modal crear/editar con cobros/reembolsos/comprobantes/links, modal "ficha", pago de grupo, panel de huésped, diálogo de recibo por email. Dividida en lógica L248-2670 (≈2.420 líneas) y JSX L2672-6118 (≈3.450 líneas); 56 `useState`, 21 `useMemo`, 9 `useEffect`, 10 `useRef`; ningún `React.memo` ni `useCallback`. · hallazgos:
  - [P1] La lista por defecto trae las 200 reservas MÁS ANTIGUAS, no las vigentes (verificado: `ReservationsPage.tsx:403-415` pide `order:"check_in"`, `limit:200`, sin `fromDate`; backend ordena `check_in_date ASC` en `app/services/reservation_service.py:2093-2094`, sin filtro de fecha por defecto, y topa en 200 en `app/api/reservations.py:559-560`). No hay `skip` ni "cargar más" en la página (grep sin resultados). Con más de 200 reservas históricas la pantalla muestra historia vieja y nunca las llegadas/ocupadas actuales salvo que se ponga un filtro de fechas. Los KPI (`:939-950`), el calendario (`:904-937`) y el historial del huésped (`:2665-2668`) se calculan sobre esa lista truncada. Además cada carga son 200 filas con 3 outer joins + consulta de huéspedes adicionales + consulta de empresas diferidas (`reservation_service.py:2035-2161`, `app/api/reservations.py:567-575`).
  - [P1] KPI "Check-outs hoy" cuenta TODA reserva `checked_out` de la lista, sin importar la fecha (verificado: `:944` `item.check_out_date === today || item.status === "checked_out"`). "Activas" incluye `no_show` (`:942`). El filtro de estado no tiene opción `no_show` (`:2979-2992`).
  - [P1] DOM duplicado: la tabla de escritorio (`:3347-3458`, `hidden md:block`) y las tarjetas móviles (`:3462-3557`, `md:hidden`) se montan a la vez; son 2 × hasta 200 = hasta 400 filas/tarjetas, cada una con 5-6 botones y varios `t()`, aunque solo una se ve (verificado por CSS-only). Sin virtualización ni filas memoizadas.
  - [P1] Re-render completo: el formulario modal (L3560-5052, ≈1.490 líneas) y el modal "ficha" (L5065-5823, ≈760 líneas) viven en el mismo componente; cada tecla en un input (`setFormValues`, `setPaymentAmountInput`, etc.) re-renderiza el componente entero incluida la lista de 400 filas de fondo. Sin `memo`/`useCallback` (grep sin resultados). Tamaño de fuente: 328.678 bytes, 54.763 gzip (medido con `wc`/`gzip`; el chunk minificado será menor, estimado, no medido). Recomendado: partir en `ReservationList` (filas memo), `ReservationFormModal`, `ReservationDetailsModal`, `GroupPaymentDialog`, `GuestPanel`, `ReceiptEmailDialog`, `AllocationPanel`, `PendingActionsPanel`, `OccupancyCalendar`, y cargar con `lazy` los modales que solo se abren por clic.
  - [P1] Requests que fallan por diseño en cada montaje: `GET /api/companies/options` exige plan "pro" (`app/api/companies.py:52-58`, `app/services/analytics_service.py:187-193` responde 402) y el frontend solo lo condiciona a `reservation:read` (`:421-426`); `GET /api/room-movement-groups/` exige `reservation:move` (`app/api/room_movement_groups.py:26-31`) y la página lo pide con cualquier sesión válida (`:572-577`), pintando "error de carga" en el panel de reasignación. El botón "Recalcular" tampoco está condicionado a permiso (`:3166-3173`; backend `reservation:move`, `reservations.py:2101-2105`). La suscripción solo se conoce con `settings:subscription:view` (`useSubscription.ts:104-107`), que el rol recepcionista por defecto no tiene (`app/services/permission_service.py:825-845`), así que `subscriptionBlocked` queda en falso y el 402 llega recién al guardar.
  - [P1] POST con efecto económico sin `Idempotency-Key` y con timeout de 60 s (`api/client.ts:66-70,747-750`) que devuelve 408 "No se pudo confirmar el resultado": crear reserva (`:1391`), crear grupo (`:1384`), agregar consumo/cargo (`:651-661,5636-5651`). El único amparo es el guard de doble clic en memoria (`useGuardedMutation`). Tras un 408 el operador puede reenviar y duplicar. El backend solo implementa la cabecera en pagos, pago de grupo y email de recibo (`app/api/payments.py:63,178`, `reservation_groups.py:121`; grep `idempot` en `reservations.py` vacío).
  - [P1] Comprobante de transferencia como base64 dentro de JSON (`:240-246`, `:2182`): sin validar `file.size` antes de leer. El backend rechaza más de 5 MB decodificados (`app/services/payment_proof_service.py:35,58`) y el schema acepta hasta 7.000.100 caracteres (`app/schemas/payment_proof.py:16`); una foto de celular de 6-8 MB se sube entera (≈33% más por base64) para recibir un error. En memoria coexisten el `File`, el data-URL y el `JSON.stringify` (estimado 3 copias). Falta redimensionar/comprimir en cliente.
  - [P2] `calendarDays` mezcla instantes UTC con hora local: compara `new Date("YYYY-MM-DD")` (UTC 00:00) con `new Date()+i` con hora del día local (`:915-923`); entre las 21:00 y las 24:00 de Argentina (UTC-3) cuenta mal ocupadas/salidas del día. Además hace 3 `filter` sobre hasta 200 reservas por día × 30 días con 2 `new Date` por elemento (≈12.000 parseos por recomputación, estimado desde `:913-925`). Etiquetas con locale fijo `es-AR` (`:929`).
  - [P2] El contador "acciones pendientes" muestra `pendingActions.length` (`:2785`), pero la query pide `limit=12` (`:418`): nunca muestra más de 12 (verificado).
  - [P2] El `<select>` "Estado" del formulario de creación está habilitado (`:4252-4269`) pero `createPayload` no envía `status` (`:1365-1380`): elegir "Check-in" o "Pago completo" no tiene efecto. Verificado.
  - [P2] `enabledPaymentMethods(undefined)` devuelve los 6 medios (incluye MercadoPago y PayPal) cuando no hay config (`:165-168`); sin `hotel_settings:read` (recepcionista por defecto, `permission_service.py:825-845`) la lista queda sin filtrar y la zona horaria cae al navegador. Inferido que ese rol es el más usado.
  - [P2] `usePaymentProofs` y `usePaymentLinks` se piden siempre al editar (`:1770-1777`) aunque la lista de comprobantes solo se muestra con método `bank_transfer` (`:4763-4863`).
  - [P2] `openRefundReview` llama `getReservation` directo, sin pasar por la caché de TanStack (`:2304`).
  - [P2] `reservation-groups`, `company-options`, `reservation-communications`, `reservation-form-availability`, `payment-fx-quote` no están en `HOTEL_ID_INDEX_BY_QUERY_PREFIX` (`src/api/queryKeys.ts`; grep de `reservation-groups` solo aparece en esta página y en `api/reservations.ts`): ninguna invalidación por dominio ni por evento los refresca. Los saldos del resumen de grupos quedan viejos tras cobrar una reserva hija hasta remontar (staleTime 15 s, `:439`). La disponibilidad del form (staleTime 10 s, `:792`) no se invalida al crear una reserva.
  - [P2] Alta de huésped automática en `handleSubmit` sin chequeo de duplicados y con nombres de relleno "Invitado"/"Sin apellido" (`:1148-1172`), a diferencia del flujo explícito de `GuestQuickCreatePanel`. Mismo patrón en `ManualOtaReservationModal.tsx:116-142`.
  - [P2] Accesibilidad/estructura: el modal de formulario (`:3561-3562`), el de ficha (`:5066-5067`) y el de huésped (`:5975-5976`) son `div` sin `role="dialog"`, sin foco atrapado ni Escape; el de pago de grupo tiene `role` pero no usa `useDialogA11y`; el de recibo reimplementa a mano un focus-trap de ≈35 líneas (`:353-388`) que ya existe en `hooks/useDialogA11y.ts`. 5 `window.confirm` nativos (`:1519,1531,1974,2136,2388`).
  - [P2] Cadenas fijas en español fuera de i18n: `:4449` "Moneda recibida", `:4510-4519` DolarAPI, `:4532`, `:4704` "Cobro parcial", `:4976`, `:5514-5530` disposición de habitación; `toLocaleString("es-AR")` fijo (`:4206,4519,4976`). Con idioma "en" se mezclan idiomas.
  - [P2] `exportVoucher` abre `window.open("")` sin `win.opener = null` (`:2415`) a diferencia de `printPaymentReceipt` (`:2478`); todo valor interpolado pasa por `escapeHtml` (verificado `:2420-2458`, `utils/escapeHtml.ts`), así que no hay XSS. Sin `dangerouslySetInnerHTML`, `localStorage`, `postMessage` ni timers recurrentes en el archivo. `toastTimeout` no se limpia al desmontar (`:699`), efecto inocuo en React 18.
  - [P2] Código muerto/duplicado: el parámetro `filters` de `useReservationMutations`/`useReservationActionMutations` se descarta (`void filters`, `useReservations.ts:167,300`) aunque la página lo pasa (`:528,571`); constantes `paymentMethodValues`/`manualPaymentMethods` duplicadas con el Drawer (`:144-152` vs `Drawer.tsx:173-179`); `guestFullName` replicado 4 veces (`Drawer.tsx:183`, `Page:198`, `GuestQuickCreatePanel.tsx:63`, `ReservationGlobalSearch.tsx:9`).
  - [P2] Dinero con `number`: sumas y conversiones en float (`:1596,1694-1700,1841-1844`) con redondeo manual a centavos y tolerancias de `+0.01` (`:1750,1966,2132`). El backend de `ReservationRead` serializa `float` (`app/schemas/reservation.py:124-158`), por lo que el cliente nunca recibe decimales exactos.
  - [info] Efecto positivo: pagos de reserva, pago de grupo y email de recibo usan `Idempotency-Key` estable por intención (`usePayments.ts:26-51`, `:540-569`, `:2577-2634`); idempotencia correcta.
  - [info] Flujo `?crear=1` valida ids y fechas antes de abrir el formulario (`:998-1033`).

- `src/components/ReservationDetailDrawer.tsx` (1.949) — Drawer lateral global (montado en AppShell vía `?reserva=`): estancia, huéspedes/acompañantes, documentos y cargos de empresa, extensión de estadía (empresa e individual con vista previa), captura de datos de check-in, cobro, check-in/parcial/out/cancelar. 27 `useState`, 9 `useEffect`, 0 `useMemo`, sin `memo`. · hallazgos:
  - [P1] Cascada de 2 etapas descrita en 1.5; la reserva no se siembra desde la lista/planilla aunque ya estaba en caché. `useValidateGuestCheckin` tiene `staleTime: 0` (`useReservations.ts:107`), así que cada apertura refetchea.
  - [P1] `checkinDataReady` exige que `guest` y `validate` terminen bien (`:334-336`) y deshabilita check-in y pre-check-in (`:1849,1864`); si cualquiera de las dos falla (403 por permisos personalizados, 404, red), el botón queda bloqueado hasta usar "reintentar" (`:1831-1843`). Además `isFetching` (no solo `isLoading`) lo apaga en cada refetch de fondo (`:330-332`).
  - [P1] Extensión de estadía con cobro inmediato o link (`:763`, `api/reservations.ts:691-699`) sin `Idempotency-Key` (el endpoint tampoco la define, `app/api/reservations.py:1668-1676`). Sí usa `client_version` (concurrencia optimista) y valida la vista previa (`:685-696`).
  - [P1] Se importa de forma estática en AppShell (`ui/AppShell.tsx:7,673-675`), por lo que sus 104.598 bytes de fuente (16.669 gzip) más las APIs de empresa/cargos viajan en el chunk del shell para todo rol con `reservation:create` o `checkin:perform`, aunque el drawer se abra pocas veces. Recomendado: `lazy()` solo cuando exista `?reserva=`.
  - [P2] La sección de cobro (`:1700-1789`), check-out y cancelar (`:1862-1899`) no comprueban permisos en la UI: `GET /api/payments/summary/{id}` exige `cash:operate` (`app/api/payments.py:143-147`), el cobro `cash:operate` (`:58-65`), check-out `checkout:perform` (`app/api/checkin.py:141-146`). Con los roles por defecto no falla (recepcionista tiene los tres), pero con roles personalizados cada apertura dispara un 403 garantizado. Inferido que existen roles personalizados.
  - [P2] `useEffect([reservationId])` limpia el formulario (`:251-255`) y `useEffect([guestQuery.data])` lo rellena (`:355-370`); al saltar entre dos reservas del mismo huésped la referencia de `data` no cambia y el formulario queda vacío tras el reset.
  - [P2] Helper de fechas propio `addIsoDays` (UTC, `:192-196`) y `candidateCompanyChargeDates` hasta 90 iteraciones por render (`:476-484`), duplican `utils/date.addDaysIso`; recalculados en cada render por no tener `useMemo`. Cálculos monetarios con `Number()`/`toFixed(2)` y tolerancias `+0.01` (`:437-451,506,812`).
  - [P2] `href={external_checkout_url}` sin validar esquema (`:1250`); la URL proviene del backend con `rel="noopener noreferrer"`. Inferido: riesgo bajo.
  - [info] Seguridad: documentos de empresa se abren como blob por `fetch` autenticado (`:565-580`) con `opener = null`; no hay tokens en URL.

- `src/api/reservations.ts` (757) — Tipos y funciones de API: reservas, cotización, grupos, check-in/out, extensión, OTA manual y planilla. · hallazgos:
  - [P1] Sin `Idempotency-Key`: `createReservation` (`:520-521`), `createReservationGroup` (`:444-449`), `addReservationCharge` (`:583-588`), `extendReservationStay` (`:691-699`). Sí la tiene `createReservationGroupPayment` (`:419-434`).
  - [P2] Tipos TS no coinciden con el backend: `ReservationGroupSummary` declara `number | null` (`:371-386`) pero el schema usa `Decimal` (`app/schemas/reservation.py:184-213`), que Pydantic v2 serializa como string en JSON (inferido, no verificado en runtime; el código lo compensa con `Number()` en `Page:1705-1709,1737`).
  - [P2] `ReservationSource` no incluye `despegar` (`:17`) mientras `ManualOtaChannel` sí (`:528`).
  - [P2] 10 tipos exportados sin ningún importador externo (verificado con script de conteo): `ReservationBillingAdjustmentSummary`, `ReservationTransactionSummary`, `ReservationFinancialSummary`, `ReservationOTALinkSummary`, `ReservationAdjustmentSummary`, `ReservationRoomMoveSummary`, `ReservationOrder`, `ReservationQuotePromotionApplied`, `ManualOtaChannel`, `ReservationExtensionResponse`; sin costo en runtime.
  - [P2] `listReservations` expone `skip`/`limit` y `upcomingOnly` pero ninguna pantalla de operación pagina (`:491-509`).
  - [info] `listReservationGroups` fija `limit=6` y hay un test que lo exige (`query-load-budget.test.mjs:64-72`).

- `src/hooks/useReservations.ts` (384) — Hooks de lectura/mutación de reservas, planilla y acciones pendientes. · hallazgos:
  - [P1] `useReservations` no hace debounce y es la query del buscador global del header (`ReservationGlobalSearch.tsx:22-24`): cada tecla desde 2 caracteres cambia la key y lanza `GET /api/reservations/?search=` (backend: `ILIKE '%term%'` sobre código de reserva y apellido con 3 joins, `reservation_service.py:2080-2088`). El `AbortSignal` cancela del lado cliente pero el servidor sigue ejecutando.
  - [P1] Todas las mutaciones refrescan "ampliamente": `refreshReservationRecordState` invalida `reservations` (todas las listas), `reservation-pending-actions`, `occupancy-grid` y `waitlist` aunque se haya tocado una sola reserva (`queryInvalidation.ts:10-17,132-169`); con `refetchType:"active"` el costo real es refetch de la lista de 200 filas + acciones pendientes + (planilla si está montada) por cada PATCH/cancelar/check-in; check-in/out añade guests y rooms (`refreshReservationGuestState`, `queryInvalidation.ts:203-207`). Un check-in desde el Drawer sobre `/reservas` refetchea ≈8 queries activas (lista 200, pendientes, reserva, operaciones, guest, validación, restricciones y `/api/rooms`, porque `includeGuests`/`includeRooms` están en `true`).
  - [P1] `usePrefetchOccupancyGrid` devuelve una función nueva en cada render (`:356-363`); en `OccupancyPlanningPage` el efecto depende de ella (`:121-126`) y se ejecuta en cada render: pasado el `staleTime` de 30 s, cualquier re-render (arrastrar una reserva, abrir el diálogo, teclear una nota) reprograma 2 requests de grillas completas (estimado: 2 grillas de 14 días × todas las habitaciones por evento).
  - [P2] `useReservation` y `useReservationOperationsSummary` con `staleTime` de 15 s (`:94,149`) y `usePaymentSummary` 30 s, mientras la lista tiene 5 min: la ficha se vuelve a pedir en cada apertura tras 15 s.
  - [P2] Código muerto: `reservationStatusLabel` (`:365-384`) sin ningún importador (grep en todo `frontend/`), y no cubre `no_show`.
  - [P2] `useReservationMutations(filters)`/`useReservationActionMutations(filters)` ignoran el parámetro (`:167,300`).
  - [P2] `usePendingReservationActions(limit)` incluye `limit` en la key (`:57-61`): Dashboard (8) y Reservas (12) hacen 2 requests distintos del mismo cálculo en backend.
  - [info] Hooks de planilla (`useOccupancyGrid`, `usePrefetchOccupancyGrid`) viven en el hook de reservas, con 3 importadores (OccupancyPlanningPage y RoomsPage).

- `src/components/ManualOtaReservationModal.tsx` (548) — Modal "Cargar reserva de OTA" (upsert por canal + id externo). · hallazgos:
  - [P2] Se monta siempre con `open={otaFormOpen}` (`Page:5054`) y sus hooks corren cerrado: `useCategories`, `useRooms`, mutaciones, `useGuestCreate` (`:79-83`); no suma requests (misma key) pero sí observadores.
  - [P2] Crea el huésped con nombres de relleno y sin chequeo de duplicados (`:116-142`), distinto del panel de alta rápida.
  - [P2] Todo el modal está en español fijo, sin i18n (`:123-547`). Montos con `Number()` float (`:157-170`).
  - [P2] Permisos: el botón solo exige `reservation:ota_record` (`Page:2739`) pero el backend exige crear+actualizar+ota_record (`app/api/reservations.py:456-466`) y `ota_payment_confirm` si se informa `amount_paid` (`:473-479`), permiso que el recepcionista no tiene; el campo se muestra a todos y el texto de MFA está fijo (`:523`).
  - [P2] El selector de habitación lista todas las de la categoría, sin considerar disponibilidad por fechas (`:98-100`); el backend valida.
  - [info] Es un upsert: reenviar canal+id actualiza (`api/reservations.ts:523-527`), por lo que el doble envío es naturalmente idempotente.

- `src/components/GuestQuickCreatePanel.tsx` (514) — Búsqueda de huésped por nombre/documento + alta rápida con detección de duplicados. · hallazgos:
  - [P1] N+1 por resultado: cada resultado de búsqueda (hasta `GUEST_SEARCH_LIMIT = 8`) renderiza `GuestRestrictionBadge` sin `hasActiveRestriction` (`:477-491`), y el badge dispara `GET guest-restrictions` por huésped (`GuestRestrictionBadge.tsx:15-18`, `useGuestRestrictions.ts:35-47`) para quien tiene `guest:prohibition_read` (recepcionista sí). Hay un endpoint por lote ya implementado (`useGuestActiveRestrictionGuestIds`, `useGuestRestrictions.ts:50-66`) que no se usa aquí.
  - [P2] Chequeo de duplicados al crear: hasta 4 requests `listGuests({search, limit: 100})` en paralelo (documento, email, teléfono, nombre) (`:233-245`); buscar solo por `first_name` devuelve hasta 100 huéspedes para comparar en cliente. Existe `GET /api/guests/search`.
  - [P2] `queryFn` de búsqueda sin `signal` (`:177`).
  - [info] Buen manejo: debounce 300 ms, mínimo 2 caracteres, `staleTime` 30 s (`:59-61,167-180`).

- `src/components/OccupancyGrid.tsx` (452) — Tabla habitación × día con arrastrar-y-soltar, bloqueos y conteos libres. · hallazgos:
  - [P1] `Cell` no está memoizado y construye en cada render un objeto con 6 llamadas a `t()` (`:202-209`); la tabla tiene habitaciones × 14 celdas (ejemplo, hipótesis de 40 habitaciones: 560 celdas × 6 = 3.360 `t()` por render, más filas de libres por categoría). El componente recibe callbacks inline (`OccupancyPlanningPage.tsx:201,211,213`) que anulan cualquier `memo` futuro.
  - [P2] `roomDropBlockedReason` se evalúa por cada celda (habitación × día) y hace `reservations.find` mientras se arrastra (`:441`, `Page:213-223`), cuando alcanzaría una vez por habitación (14× redundante).
  - [P2] El comentario de cabecera dice "30 by default" (`:8`) pero `WINDOW_DAYS = 14` (`OccupancyPlanningPage.tsx:18`).
  - [P2] `categoryGroups` se calcula siempre aunque `sortMode` sea "category" (`:308`); `new Date(...)` por encabezado en cada render (`:342`).
  - [P2] Cadenas fijas "Sin asignar", "reserva(s) sin habitación", "Hab.", "Piso" (`:351-352,426-427`).
  - [P2] Duplicado: `components/marketing/ui/OccupancyBoard.tsx` (210 líneas) es una "copia fiel" declarada de este componente (`OccupancyBoard.tsx:9`).
  - [info] Sin virtualización, documentado y razonable para decenas de habitaciones (`:8-11`).
  - [info] Arrastrar solo funciona con mouse (HTML5 DnD), sin teclado ni táctil (`:181-183`).

- `src/views/protected/OccupancyPlanningPage.tsx` (336) — Planilla de ocupación por ventanas de 14 días con prefetch y movimiento por arrastre. · hallazgos:
  - [P1] Prefetch en efecto con dependencia inestable (ver `useReservations.ts`): 2 grillas completas extra en cada render pasados 30 s, más las 3 iniciales (`:121-126`); cada grilla repite `rooms` completo (`OccupancyGridResponse`, `api/reservations.ts:743-748`). El backend sí cachea la grilla (`app/services/read_model_cache.py:349-361`) y limita a 92 días (`reservations.py:772-773`).
  - [P2] `useRooms()` (2 requests: habitaciones y categorías) solo sirve para `roomById` y `max_occupancy` (`:43,55-65`), datos que la grilla ya trae (`rooms[].category_id`); los `max_occupancy` sí faltan en la grilla. Evitable agregando `max_occupancy` al payload.
  - [P2] `windowStart` se fija con `useState(todayIso())` (`:28`) y no avanza al pasar la medianoche con la pantalla abierta (recepción); `today` sí se recalcula (`:31`).
  - [P2] Imports de `addDaysIso`/`todayIso` vía `hooks/useRateCalendar` (reexport, `:13`) en vez de `utils/date`: arrastra el módulo del calendario de tarifas a este chunk.
  - [P2] El diálogo de movimiento tiene `role="dialog"` pero no usa `useDialogA11y` (sin Escape ni foco atrapado, `:227-333`); motivos de movimiento en español fijo (`utils/roomMove.ts`).
  - [info] Sin polling; la invalidación llega por eventos (`refreshReservationState` tras mover, `:91-99`).

---

## 3. Verificaciones de "no se usa / no existe"

- `reservationStatusLabel`: 0 importadores (grep en `frontend/`; solo la definición, `useReservations.ts:365`).
- `refetchInterval`: 0 usos en todo `frontend/src`.
- `React.memo`/`useCallback`: 0 en los 8 archivos asignados.
- `dangerouslySetInnerHTML`/`localStorage`/`sessionStorage`/`postMessage`/`setInterval`/`EventSource`/`BroadcastChannel` en los 8 archivos: 0 (solo un WebSocket indirecto de `useCollaborativeResource` y `setTimeout` para toast/debounce).
- Importadores de `OccupancyGrid`: solo `OccupancyPlanningPage` (más la copia de marketing por texto en comentario).
- `useValidateGuestCheckin`: único consumidor, el Drawer.

## Resumen de la parte

1. [P1] `/reservas` carga por defecto las 200 reservas MÁS ANTIGUAS (`order=check_in` ASC, `limit=200`, sin fechas ni paginación), y de esa lista truncada salen KPIs, calendario e historial; con más de 200 reservas la pantalla deja de mostrar lo vigente (`ReservationsPage.tsx:403-415`, `reservation_service.py:2093`). Mismo patrón en `StockPage.tsx:203`.
2. [P1] ReservationsPage es un monolito de 6.120 líneas (56 `useState`, 25 sitios de llamada de query (26 observadores), 0 memo): cada tecla re-renderiza todo y la lista se monta duplicada (tabla + tarjetas, hasta 400 filas, `:3347-3558`). Dividir y cargar modales con `lazy`.
3. [P1] KPI incorrectos: "Check-outs hoy" cuenta todas las `checked_out` históricas (`:944`), "Activas" incluye `no_show`, el calendario mezcla UTC y hora local (`:915-923`).
4. [P1] El buscador global del header dispara una request por tecla sin debounce, con `ILIKE '%…%'` y 3 joins en backend (`ReservationGlobalSearch.tsx:22-24`, `useReservations.ts:69-84`, `reservation_service.py:2080-2088`).
5. [P1] Requests que fallan por diseño en cada montaje de `/reservas`: `companies/options` (402 en planes bajo "pro") y `room-movement-groups` (403 sin `reservation:move`), más botón de reasignación sin gate de permiso (`:421-426,572-577,3166`).
6. [P1] El Drawer abre con 3 requests + cascada de 3 a 7 más (guest, validate-checkin con `staleTime 0`, restricciones, datos de empresa) porque no siembra la caché con la reserva ya cargada (`ReservationDetailDrawer.tsx:257-328`), y su carga estática de 104 KB entra al chunk del shell para todos los roles (`AppShell.tsx:7`).
7. [P1] POST con dinero o altas sin `Idempotency-Key` ante timeouts de 60 s: crear reserva/grupo, cargos, extensión con cobro inmediato (`api/reservations.ts:444-449,520-521,583-588,691-699`).
8. [P1] Planilla: prefetch con identidad inestable (2 grillas extra por render pasados 30 s), celdas sin memo con 6 `t()` c/u, `roomDropBlockedReason` por celda, `rooms` repetido en cada ventana y `RoomsPage` pidiendo 92 días (`useReservations.ts:356-363`, `OccupancyGrid.tsx:202-209,441`, `RoomsPage.tsx:91`).
9. [P1] Comprobantes de transferencia como base64 en JSON sin validar tamaño en cliente (backend máximo 5 MB): subidas de hasta ≈7 MB desperdiciadas y 3 copias en memoria (`ReservationsPage.tsx:240-246,2182`, `payment_proof_service.py:35`).
10. [P1] Carga inicial: `i18n.ts` importa estáticamente `reservations.json` en `es` y `en` (63.350 + 65.843 = 129.193 bytes, 33.378 gzip medidos) dentro del chunk de entrada (`i18n.ts:10,18`; `main.tsx:9`), aunque solo lo usan `/reservas`, el Drawer y la planilla. Referencia cruzada para la parte de bundle.
