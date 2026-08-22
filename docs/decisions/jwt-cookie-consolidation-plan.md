# TECH-0021 — Plan de consolidación JWT bearer y cookie de sesión

**Estado:** propuesta para decisión humana; no se elimina ni se depreca el bearer JWT en este cambio.
**Fecha de auditoría:** 2026-08-21
**Código auditado:** `8a53fc3` (`origin/main` en este worktree)
**Alcance:** inventario de consumidores, revocación cruzada y recomendación de corte. El cambio local sólo corrige la revocación cruzada y documenta los límites actuales.

## Resumen ejecutivo

El bearer JWT no es código muerto. El frontend actual conserva el `access_token` en memoria y `frontend/src/api/client.ts:75-101` construye `Authorization: Bearer <token>` para las peticiones autenticadas. El interceptor de `frontend/src/api/client.ts:249-281` reintenta un `401` usando la sesión cookie, recibe un JWT nuevo y vuelve a enviar bearer. El login continúa devolviendo el JWT y creando la sesión cookie en `app/api/auth.py:145-207`.

Por lo tanto, no es seguro retirar el mecanismo JWT en esta tarea. La cookie server-side es la autoridad de ciclo de vida/refresh del navegador durante la transición de TECH-0021, pero el bearer sigue siendo el mecanismo que autoriza las requests operativas del SPA y también queda disponible para clientes first-party nativos/automatizados.

## Hallazgo confirmado de consumidores

### Frontend web y clientes first-party

- `frontend/src/api/client.ts:86-101` agrega `Authorization` y el token bearer junto con `X-Hotel-Id`/`X-User-Id`.
- `frontend/src/api/client.ts:220-246` usa `credentials: "include"` y CSRF para renovar la sesión cookie.
- `frontend/src/api/client.ts:249-281` envía bearer en la request normal y, ante `401`, renueva por cookie y repite la request con el nuevo bearer.
- `frontend/src/state/session.tsx:175-199` toma `response.access_token`, lo conserva sólo en memoria y mantiene sincronizado el cliente API.
- `frontend/e2e/guest-pagination.spec.ts:30-57` es evidencia adicional de un cliente de API first-party que toma el token de login y lo reenvía como bearer.
- La misma implementación de API se usa en el shell Capacitor (`frontend/README.md:28-30`, `frontend/capacitor.config.ts`); no hay evidencia en este checkout de una migración nativa separada que elimine bearer.

El grep directo de `Authorization|Bearer` en `frontend/src` no fue vacío: encontró la construcción real en `frontend/src/api/client.ts:100` y usos de credenciales de proveedores en settings. Los textos `Bearer token` de WhatsApp/Mercado Pago son credenciales de integraciones externas, no JWT de este backend.

### Superficies públicas e integraciones externas

- `/api/public/booking` depende de `require_web_engine_api_context` y `X-API-Key` (`app/dependencies/api_key_auth.py:35-71`, `app/api/public_booking.py:1-45`); no depende de JWT bearer.
- `/api/public/whatsapp` usa la API key hotel-scoped de propósito `WHATSAPP_BOT` (`app/dependencies/api_key_auth.py:129-130`, `app/api/whatsapp_hooks.py:29-38,106-111`); no depende de JWT bearer.
- OTA entrantes (`app/api/ota_webhooks.py:15-64`) usan `hotel_id` más `webhook_secret` y validación de credencial por hotel.
- Webhooks de Mercado Pago (`app/api/payment_links.py:113-143`, `app/api/payment_link_tests.py:130-150`) validan firma del proveedor; no usan JWT de usuario.
- Los `Authorization: Bearer` encontrados en `app/services/integration_service.py`, `gemma_*` y servicios de pagos son tokens entregados por proveedores externos para llamadas salientes. No son consumidores del JWT firmado por `create_access_token`.

No se encontró una integración externa entrante documentada que dependa del JWT normal de usuario. Sí se encontraron clientes first-party de API, por lo que la condición de código muerto no se cumple.

## Bug de revocación cruzada y corrección aplicada

Antes de este cambio, `app/dependencies/auth.py:82-87` comprobaba `token_version` sólo si algún flujo lo incrementaba, mientras `/api/auth/logout` revocaba la fila `UserSession` y limpiaba cookies sin incrementar esa versión. En consecuencia, un JWT robado emitido por el mismo login seguía autorizando requests después del logout. El test existente `tests/test_user_sessions.py:245-294` incluso verificaba ese comportamiento (`/api/auth/me` seguía devolviendo `200`).

La corrección local es mínima y backward-compatible con la forma de login/logout:

1. `POST /api/auth/logout` incrementa `user.token_version` cuando revoca una sesión cookie válida.
2. `DELETE /api/auth/sessions/{session_id}` incrementa la misma versión cuando revoca una sesión server-side.
3. Los JWT viejos quedan rechazados por el check existente de `app/dependencies/auth.py:82-87`.
4. Las cookies de otras sesiones no se revocan. El frontend puede renovarlas por `/api/auth/session/refresh` y recibir un JWT con la nueva versión.
5. Se agregó regresión en `tests/test_user_sessions.py:245-305`: bearer viejo rechazado tras revoke/logout y sesión cookie vigente capaz de refrescarse.

La granularidad sigue siendo user-scoped porque `token_version` pertenece a `User`, no a `UserSession`. Por eso un revoke individual invalida los bearer emitidos para ese usuario; la cookie de los otros dispositivos permanece vigente y puede recuperarse por refresh. Si el producto exige revocación JWT estrictamente por dispositivo sin invalidar otros bearers, hace falta una decisión y un diseño posterior de claim/session binding, no un borrado silencioso del mecanismo actual.

## Recomendación para decisión humana

Recomiendo mantener por ahora el esquema híbrido explícito:

- cookie HttpOnly + CSRF para ciclo de vida, refresh, logout y gestión de sesiones del navegador;
- bearer JWT para requests operativas actuales del SPA y clientes first-party nativos/automatizados;
- API keys y secretos/firmas separados para superficies públicas y webhooks.

El corte final de TECH-0021 debe decidirse explícitamente por el dueño del producto entre:

1. mantener el híbrido y formalizar contratos/telemetría para cada cliente bearer;
2. migrar cada cliente no navegador a una sesión/token específico antes de retirar el bearer normal;
3. diseñar tokens ligados a `UserSession` si se necesita revocación por dispositivo, con migración backward-compatible y pruebas de clientes existentes.

No recomiendo eliminar `access_token`, `Authorization: Bearer` ni `decode_access_token` hasta cerrar ese inventario con evidencia de clientes móviles/API y un plan de migración aprobado.

## Fuentes y nivel de certeza

**Confirmado por código y tests locales:** frontend web envía bearer; login devuelve JWT y crea cookie; refresh usa cookie/CSRF; rutas públicas usan API keys; webhooks usan secretos o firmas; logout/revoke ahora incrementan `token_version`; la regresión está expresada en `tests/test_user_sessions.py`.

**Needs-verification antes del corte final:** clientes móviles instalados fuera del checkout, consumidores externos no versionados en este repositorio, métricas de uso real de bearer y si la granularidad user-scoped del token version es aceptable para revocación individual.

El comando literal `.venv/bin/python -m pytest -q` no pudo ejecutarse porque `.venv/bin/python` no existe en este worktree y el Python del sistema no tiene `pytest`. Como validación equivalente, el mismo checkout pasó `.../.venv/bin/python -m pytest -q` con `1673 passed, 22 skipped, 12 xfailed, 1 xpassed, 0 failures`; la decisión de arquitectura sigue abierta y por eso este documento continúa en estado de propuesta.
