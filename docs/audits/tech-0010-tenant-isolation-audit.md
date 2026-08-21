# TECH-0010 — Auditoría de aislamiento multi-hotel

Fecha: 2026-08-21  
Checkout auditado: `codex/tech0010-isolation-audit-closure`  
SHA base auditado: `6fd71f08de84b5c891b9ea9e47d8f802831f964f`  
Estado: `VERIFY` parcial; no se marca `VERIFIED` porque todavía hay rutas sin una prueba cross-tenant individual.

## Alcance y método

Se inspeccionaron las rutas registradas por `app/api/` mediante AST y el código real de handlers, servicios y dependencias. El inventario contiene 418 registros de ruta, correspondientes a 375 handlers únicos: 380 registros reciben `AuthContext`, 3 reciben `hotel_id` directo para webhooks OTA y 35 son rutas de identidad, callbacks firmados, webhooks, demo, health, referencia o código legacy sin contexto operacional.

La resolución normal de tenant está centralizada en `app/dependencies/auth.py:105-150`: el usuario se autentica, se cargan memberships activas, `X-Hotel-Id`/el claim sólo seleccionan una membership existente y el `AuthContext.hotel_id` se deriva server-side. Los permisos se evalúan con ese mismo hotel en `app/dependencies/auth.py:153-187`. Un `hotel_id` de request no se usa como autoridad en las rutas operativas.

Reglas de estado de esta matriz:

- `VERIFIED`: el lookup aplica el hotel server-side y existe una regresión cross-tenant que prueba esa superficie.
- `VERIFY`: el código aplica el hotel server-side, pero falta una prueba negativa dedicada para cada operación/ruta agrupada.
- `TODO`: gap concreto confirmado. No quedó ninguno abierto después del fix financiero de esta auditoría.
- Las rutas con credencial externa firmada se separan: no tienen membership de usuario por diseño, pero deben validar la credencial y el tenant embebido.

## Matriz completa de rutas tenant-scoped

Las rutas con `/` y sin `/`, y los aliases de compatibilidad, apuntan al mismo handler y por eso se muestran en una sola celda; el inventario AST contabilizó ambos registros.

| Endpoint(s) / handler(s) | Estado | Evidencia de aislamiento |
|---|---|---|
| `/api/allocation/policy*` (12 handlers) | VERIFY | Todos inyectan contexto; las operaciones reciben `hotel_id=context.hotel_id` en `app/api/allocation_policy.py:142-317`; los runs/suggestions se consultan por hotel en `app/services/allocation_policy_service.py`. |
| `/api/analytics/*` (26) | VERIFY | Contexto en cada handler; detalles de room/category/company y exports se pasan con hotel; los lookups de recursos están filtrados en `app/services/analytics_service.py:362-365,752-754,1080-1084,1146-1153` y `app/services/analytics_exports.py:534`. |
| `/api/auth/me` | VERIFY | Única ruta auth operacional: `app/api/auth.py:959-966` recibe `get_auth_context`; el resto de auth es identidad/sesión, no lectura de recursos hoteleros. |
| `/api/bookings/*` (11) | VERIFY | `app/api/bookings.py:165-202,281-321` filtra reservations, category y room con `context.hotel_id`; faltan negativos dedicados para todas las transiciones. |
| `/api/cash-register/*` y aliases legacy (18) | VERIFY | Todos reciben contexto; el servicio compone cada lookup por hotel, incluidos session, transaction y close report: `app/services/cash_register_service.py:118,256,387,411,421`. |
| `/api/checkin/*` (4) | VERIFY | `app/api/checkin.py:183-188` valida el guest por `guest_id + context.hotel_id`; las reservas se resuelven mediante servicios tenant-scoped. |
| `/api/commercial/*` (12) | VERIFY | Handlers pasan `context.hotel_id` (`app/api/commercial.py:50-193`); get/update helpers aplican la pareja id/hotel en `app/services/commercial_service.py:186-240`. |
| `/api/companies/*` (6) | VERIFY | Handlers pasan `context.hotel_id` (`app/api/companies.py:40-90`); creación y mutación usan `_get_*` tenant-scoped en `app/services/analytics_service.py:362-368`. |
| `/api/company-documents/*` (6) | VERIFY | `_get_document_or_404` exige `document_id + hotel_id` en `app/api/company_documents.py:27-38`; listados por company/reservation se filtran por contexto. |
| `/api/config/*` (3) | VERIFY | `app/api/config.py:19-47` sólo opera sobre el config obtenido desde `context.hotel_id`; no acepta hotel_id del payload. |
| `/api/rates/*` (9) | VERIFY | Category/period lookups exigen hotel: `app/api/daily_rates.py:159-163,604-612,660-668`; bulk writes reciben `context.hotel_id`. |
| `/api/events/stream` | VERIFY | `app/api/events.py:22` recibe contexto; el stream usa el hotel del actor. |
| `/fx/*` (5) | VERIFY | Snapshot/listado se limitan a `context.hotel_id` en `app/api/fx_rates.py:161,189`; falta un test negativo dedicado para snapshot histórico. |
| `/api/gemma/chat/*` (10) | VERIFY | Todas las operaciones pasan `context.hotel_id` al orquestador; no se acepta scope de hotel en el payload. |
| `/api/guests/*` (13) | VERIFY | Detail/update/companions consultan `Guest.id + Guest.hotel_id` en `app/api/guests.py:205-210,328-365`; ledger/search filtran por contexto. |
| `/api/guests/{guest_id}/restrictions*` (3) | VERIFY | `_get_tenant_guest` exige `guest_id + hotel_id` en `app/api/guest_restrictions.py:31-36`; restrictions también filtran `context.hotel_id` en línea 80. |
| `/api/hotel-api-keys*` (3) | VERIFY | issue/list/revoke pasan `context.hotel_id` (`app/api/hotel_api_keys.py:23-56`); el servicio usa id + hotel en `app/services/hotel_api_key_service.py:71,99,117`. |
| `/api/integrations` y callbacks manuales (6) | VERIFY | Operaciones autenticadas usan `context.hotel_id`; `_find_integration` y mutaciones filtran por hotel en `app/api/integrations.py:476-509` y `app/services/integration_service.py:522-553`. |
| `/api/laundry/batches*` (5) | VERIFY | Cada handler pasa contexto; `get_batch` usa `batch_id + hotel_id` en `app/services/laundry_service.py:91-108`. |
| `/api/laundry/items`, locations, movements, vendors, remitos y settlements (19) | VERIFY | Todos los handlers pasan `context.hotel_id` (`app/api/laundry_vendor.py:256-564`); vendor, price, remito y settlement helpers filtran por hotel en `app/services/laundry_vendor_service.py:75,130,256,273,358,432`. |
| `/api/movement-groups*` (4) | VERIFY | List/detail/revert reciben contexto; `app/api/movement_groups.py:121` y el service filtran `RoomMovementGroup.hotel_id`. |
| `/api/notifications*` (9) | VERIFY | Todas las llamadas pasan `hotel_id=context.hotel_id` y `user_id=context.user_id` (`app/api/notifications.py:40-172`); falta una prueba negativa dedicada para notification id. |
| `/api/onboarding/*` (11) | VERIFY | Todos los writes pasan exclusivamente `hotel_id=context.hotel_id` (`app/api/onboarding.py:33-150`); los servicios upsert filtran por hotel. |
| `/api/payment-link-tests` autenticado (8) | VERIFY | list/create/refresh/cancel usan `context.hotel_id`; los servicios filtran `PaymentLinkTest.hotel_id` en `app/services/payment_link_test_service.py:354-359,363-367,420-433`. |
| `/api/payment-links*` autenticado (6 handlers, 8 aliases) | VERIFY | create/list/cancel pasan context; reservation/link queries exigen hotel en `app/services/payment_link_service.py:172,476,483,522`. El webhook se documenta aparte. |
| `/api/payment-proofs*` (7 registros, 5 handlers) | VERIFY | Handlers pasan hotel (`app/api/payment_proofs.py:37-113`); service filtra proof/blob/reservation por hotel. Hay pruebas ID-collision de image/approve, pero no para cada alias/list/reject. |
| `/api/payment-surcharges*` (6) | VERIFY | list/update/delete filtran `PaymentSurcharge.hotel_id` en `app/api/payment_surcharges.py:130-149,197-261`. |
| `POST /api/payments`, `POST /api/payments/`, `GET /api/payments/summary/{reservation_id}` | VERIFIED | Fix de esta auditoría: `process_payment` y `get_reservation_financial_summary` filtran `Reservation.id + Reservation.hotel_id` y devuelven `PaymentNotFoundError` sin revelar el tenant en `app/services/payment_service.py:237-249,526-536`; la API traduce a 404 en `app/api/payments.py:31-58`. Cubierto por `tests/test_cross_hotel_id_collision_api.py`. |
| `/api/permissions/*` (20 handlers) | VERIFIED | `_target_membership_or_404` exige `hotel_id + user_id + active` en `app/api/permissions.py:103-110`; regresión de usuario de Hotel A contra membership de B en `tests/test_cross_hotel_id_collision_api.py`. |
| `/api/promotions*` (9) | VERIFY | CRUD/simulate pasa contexto y `app/services/promotion_service.py:38-50,227-278` filtra promotion/guest tag por hotel; falta cobertura negativa para todos los cambios de estado. |
| `/api/public/booking/*` (10) | VERIFY | `require_web_engine_api_context` deriva hotel desde API key; queries directas usan `context.hotel_id` (`app/api/public_booking.py:53-199`). No es membership humana; requiere pruebas adicionales de API-key de Hotel A contra category/reservation B. |
| `/api/rate-calendar/daily` | VERIFY | `app/api/rate_calendar.py:19-28` pasa context; `app/services/rate_calendar_service.py:61-67` filtra category por hotel. |
| `/api/reports/*` (6) | VERIFY | Daily/occupancy/revenue filtran reservation, room y transaction por `context.hotel_id` en `app/api/reports.py:126-160,265-342`. |
| `/api/reservations*` (24 registros, 21 handlers) | VERIFY | Rutas por id usan `get_reservation_by_id(db, id, context.hotel_id)` (`app/api/reservations.py:464-506,620-1101`); helper aplica `Reservation.id + hotel_id` en `app/services/reservation_service.py:1394-1402`. Hay pruebas de read/grid, no una negativa dedicada para cada mutación. |
| `/api/room-blocks*` (4) | VERIFY | Service exige room/block id + hotel en `app/services/room_block_service.py:108,156,165`; handlers pasan contexto. |
| `/api/room-movement-groups*` (4 registros, 3 handlers) | VERIFY | Service exige group/event/room id + hotel en `app/services/room_movement_group_service.py:24-34,143-148`; read/revert cross-hotel existente. |
| `/api/room-state-events*` (3) | VERIFY | list filtra `RoomStateEvent.hotel_id` en `app/api/room_state_events.py:33`; create/close pasan contexto al service. |
| `/api/rooms/*` (18) | VERIFIED | Category/room lookups exigen id + `context.hotel_id` en `app/api/rooms.py:122,182,214,350-424,572-695`; read/update cross-hotel y category cross-hotel cubiertos en la suite ID-collision. |
| `/api/settings/security/*` (5) | VERIFIED | overview/events filtran `SecurityAuditLog.hotel_id` (`app/api/settings_security.py:96-131`); timeline aplica el mismo filtro a las tres fuentes en `app/services/audit_timeline_service.py:81,152,171,193`; evento cross-hotel cubierto. |
| `/api/stock/*` (16) | VERIFY | Handlers pasan hotel (`app/api/stock.py:159-385`); item/location/movement helpers exigen hotel en `app/services/stock_service.py:42,115,214,284,451`. ID-collision cubre parte de read/write. |
| `/api/admin/subscription/*` (8) | VERIFY | Rutas normales derivan hotel de `AuthContext`; el único `hotel_id` de body es `POST /api/admin/subscription/comped-override`, autorizado por `require_platform_admin()` y validado contra `HotelConfiguration` en `app/api/subscription.py:174-210`. Es una operación cross-tenant intencional de plataforma, no una membership de hotel. |
| `/api/users/*` (7) | VERIFIED | invitation/user lookups filtran `StaffInvitation/HotelMembership.hotel_id == context.hotel_id` (`app/api/users.py:279-366,420-524`); resend de invitación B probado desde A. |
| `/api/waitlist*` (9 registros, 6 handlers) | VERIFY | Todos pasan context a `app/services/waitlist_service.py`; falta un test negativo de entry id y promotion. |
| `/api/public/whatsapp/*` (9) | VERIFY | `require_whatsapp_api_context` deriva hotel desde credencial; handlers nunca usan hotel del body y pasan `context.hotel_id` (`app/api/whatsapp_hooks.py:43-125`). Hay tests de aislamiento de create/payment-link, faltan todos los read paths. |

## Rutas fuera del contexto de membership humana

| Ruta | Estado | Control real |
|---|---|---|
| `POST /api/webhooks/{booking,expedia,despegar}/{hotel_id}/{webhook_secret}` | VERIFY | El path selecciona hotel, pero `_resolve_webhook_credential` exige credential activa, hash secreto y coincide cualquier `payload.hotel_id`/property en `app/services/ota_service.py:107-145`. Falta prueba HTTP negativa por cada proveedor con secret de otro hotel. |
| `GET /api/integrations/oauth/{provider}/callback` | VERIFY | State firmado contiene hotel/user/integration y `_authorize_oauth_state_actor` se ejecuta antes de guardar código (`app/api/integrations.py:422-457`). Falta test de state firmado para otro hotel. |
| `GET/POST /api/invitations/{token}[/{accept}]` | VERIFY | Token persistente hasheado se resuelve antes de cargar `invitation.hotel_id`; aceptación valida identidad y membership del hotel en `app/api/invitations.py:43-190`. Es una credencial de invitación, no una sesión Hotel A; falta test de token B usado por actor A. |
| `POST /api/payment-links/mercadopago/webhook` y alias sin `/api` | VERIFY | Firma externa se valida antes de `resolve_signed_external_reference`; el external reference firmado contiene hotel y link en `app/api/payment_links.py:86-143` y `app/services/payment_link_service.py:sign_external_reference`. Falta test de firma/reference cruzados. |
| `POST /api/payment-link-tests/mercadopago/webhook` | VERIFY | Firma de Mercado Pago se valida antes de resolver reference; el `hotel_id` query sólo agrega filtro en `app/api/payment_link_tests.py:97-150` y el service filtra reference/provider/hotel. Falta prueba con query hotel B contra reference A. |
| `POST /api/connections/{provider}/connect` | VERIFIED (no viva) | Router legacy no está incluido en `app/main.py`; la ruta devuelve 410/404 y está cubierta por `tests/test_multi_hotel_isolation_contracts.py`. |
| `/api/auth/*` excepto `/api/auth/me` | VERIFY / control de identidad | No reciben recursos operativos por hotel. Login y respuesta de auth construyen el hotel elegido desde memberships en `app/api/auth.py:130-142`; sesiones/MFA/reset son user-scoped, no tenant-resource endpoints. |
| `/api/seed`, `/api/reset`, `/api/email/*`, `/health/datastores`, `/api/reference/timezones` | CONTROL | No reciben ni resuelven un `hotel_id` operativo; demo está condicionado a `DEMO_MODE`, health/reference son globales y email es auth. |

## Gap encontrado y corregido

Hallazgo: dos endpoints (`POST /api/payments[ / ]` y `GET /api/payments/summary/{reservation_id}`) cargaban primero por ID global y recién después comparaban el hotel. El rechazo evitaba una mutación cruzada, pero el status 400 y el mensaje permitían confirmar la existencia del recurso y el hotel ajeno.

Fix mínimo:

- `app/services/payment_service.py`: lookup compuesto por `Reservation.id` y `Reservation.hotel_id` cuando existe contexto; `Transaction.hotel_id` también queda scoped; `PaymentNotFoundError` usa mensaje genérico.
- `app/api/payments.py`: `PaymentNotFoundError` se traduce a 404; no se devuelve el id de hotel ni datos de la reserva.
- `tests/test_cross_hotel_id_collision_api.py`: agrega read/write financiero, query param de payment links, invitación, RBAC y audit log; todos comprueban ausencia de datos de Hotel B.
- No se tocó RLS, base real, cuentas cloud, migraciones ni infraestructura.

El SHA exacto del fix queda **pendiente** porque Git no pudo crear el lock de índice fuera del workspace writable (`/Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS/.git/worktrees/codex-tech0010-isolation-audit/index.lock`, `Operation not permitted`). El commit convencional, push y PR deben ejecutarse cuando la metadata Git sea writable.

## Pruebas y cobertura

Regresiones nuevas o extendidas: reservas, huéspedes, habitaciones, categorías, caja, payment links, payments, payment proofs, invitaciones, permisos/RBAC y audit events; también se conserva la cobertura existente de occupancy/export/company documents/room movement/guest restrictions/public APIs.

La suite solicitada `.venv/bin/python -m pytest -q` no pudo ejecutarse en este entorno porque el worktree no traía `.venv`, y la instalación de `requirements.txt` con `uv` falló por DNS/red restringida al acceder a PyPI (`https://pypi.org/simple/httpx/`). Se validó sintaxis de los archivos modificados con Python 3.12 del entorno creado. Esto mantiene el estado `VERIFY` y es un bloqueo de validación, no evidencia de verde.

## Conclusión TECH-0010

TECH-0010 **no puede pasar a `VERIFIED` todavía**. El código operativo resuelve membership/hotel server-side y el gap concreto encontrado fue corregido; no quedó ningún `TODO` confirmado en las rutas auditadas. El estado correcto es **`VERIFY` parcial**: faltan pruebas negativas dedicadas para todas las familias marcadas `VERIFY`, en particular laundry/linen, notifications, analytics exports, integrations OAuth, OTA/webhooks, public API-key paths, WhatsApp read paths, waitlist, room blocks, rates y todas las mutaciones de reservations/bookings.

Backlog de cierre: ejecutar pytest completo en un entorno con dependencias, agregar esas pruebas por familia, repetir la matriz contra el SHA final y publicar el PR; la evidencia RLS real de PostgreSQL continúa siendo defensa adicional y no fue modificada ni reclamada como validada aquí.
